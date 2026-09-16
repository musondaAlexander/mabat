from __future__ import annotations

import json
from collections import namedtuple
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import mabat
from mabat._shared import config
from mabat._shared import platform as plat
from mabat._shared.models import ProblemKind, Problems
from mabat.sections.cpu import collector, identity
from mabat.sections.cpu.models import CpuIdentity, CpuUsage

FULL_CPUINFO: dict[str, Any] = {
    "brand_raw": "Fake CPU 9000",
    "vendor_id_raw": "GenuineFake",
    "arch": "X86_64",
    "bits": 64,
    "hz_advertised": [3_000_000_000, 0],
    "family": 25,
    "model": 80,
    "stepping": 0,
    "l1_data_cache_size": "32 KB",  # old py-cpuinfo string form
    "l1_instruction_cache_size": 32768,
    "l2_cache_size": 524288,
    "l3_cache_size": 16 * 1024 * 1024,
    "flags": ["avx2", "sse4_2"],
}


@pytest.fixture(autouse=True)
def _no_identity_cache() -> Iterator[None]:
    identity.clear_cache()
    yield
    identity.clear_cache()


def _powershell_result(stdout: str) -> plat.CommandResult:
    return plat.CommandResult(args=("powershell",), returncode=0, stdout=stdout, stderr="")


# --- identity --------------------------------------------------------------------


def test_identity_from_full_cpuinfo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity, "_cpuinfo_raw", lambda: (FULL_CPUINFO, None))
    problems = Problems()
    ident = identity.read_identity(problems)
    assert isinstance(ident, CpuIdentity)
    assert ident.brand == "Fake CPU 9000"
    assert ident.advertised_hz == 3_000_000_000
    assert ident.cache.l1_data_bytes == 32 * 1024  # parsed from "32 KB"
    assert ident.cache.l3_bytes == 16 * 1024 * 1024
    assert ident.flags == ("avx2", "sse4_2")
    assert ident.logical_cores and ident.logical_cores > 0
    assert not [p for p in problems.freeze() if p.source.startswith("cpuinfo")]


def test_identity_falls_back_when_cpuinfo_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity, "_cpuinfo_raw", lambda: (None, "py-cpuinfo is not installed"))
    monkeypatch.setattr(plat, "IS_WINDOWS", False)
    problems = Problems()
    ident = identity.read_identity(problems)
    assert ident.architecture  # from platform.machine()
    assert ident.bits in (32, 64)
    assert ident.logical_cores and ident.logical_cores > 0  # psutil / os.cpu_count
    kinds = {(p.source, p.kind) for p in problems.freeze()}
    assert ("cpuinfo", ProblemKind.MISSING_DEPENDENCY) in kinds
    assert ("cpuinfo.cache", ProblemKind.NOT_PRESENT) in kinds


def test_wmi_fills_missing_cache_levels_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = {**FULL_CPUINFO}
    del raw["l3_cache_size"]
    monkeypatch.setattr(identity, "_cpuinfo_raw", lambda: (raw, None))
    monkeypatch.setattr(plat, "IS_WINDOWS", True)
    monkeypatch.setattr(
        plat,
        "run_powershell",
        lambda script, **kw: _powershell_result('{"L2CacheSize":512,"L3CacheSize":16384}'),
    )
    ident = identity.read_identity(Problems())
    assert ident.cache.l2_bytes == 524288  # cpuinfo value kept
    assert ident.cache.l3_bytes == 16384 * 1024  # WMI KiB -> bytes


def test_wmi_handles_multi_socket_list(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = {k: v for k, v in FULL_CPUINFO.items() if k != "l3_cache_size"}
    monkeypatch.setattr(identity, "_cpuinfo_raw", lambda: (raw, None))
    monkeypatch.setattr(plat, "IS_WINDOWS", True)
    monkeypatch.setattr(
        plat,
        "run_powershell",
        lambda script, **kw: _powershell_result('[{"L3CacheSize":8192},{"L3CacheSize":8192}]'),
    )
    assert identity.read_identity(Problems()).cache.l3_bytes == 8192 * 1024


def test_wmi_failure_is_a_problem_not_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = {k: v for k, v in FULL_CPUINFO.items() if k != "l3_cache_size"}
    monkeypatch.setattr(identity, "_cpuinfo_raw", lambda: (raw, None))
    monkeypatch.setattr(plat, "IS_WINDOWS", True)

    def failing(script: str, **kw: object) -> plat.CommandResult:
        raise plat.CommandNotFoundError("'powershell' is not installed or not on PATH")

    monkeypatch.setattr(plat, "run_powershell", failing)
    problems = Problems()
    ident = identity.read_identity(problems)
    assert ident.cache.l3_bytes is None
    sources = {p.source for p in problems.freeze()}
    assert {"wmi.Win32_Processor", "cpuinfo.cache"} <= sources


def test_wmi_not_consulted_off_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = {k: v for k, v in FULL_CPUINFO.items() if k != "l3_cache_size"}
    monkeypatch.setattr(identity, "_cpuinfo_raw", lambda: (raw, None))
    monkeypatch.setattr(plat, "IS_WINDOWS", False)
    calls: list[str] = []
    monkeypatch.setattr(plat, "run_powershell", lambda script, **kw: calls.append(script))
    problems = Problems()
    identity.read_identity(problems)
    assert not calls
    assert {p.source for p in problems.freeze()} == {"cpuinfo.cache"}


@pytest.mark.parametrize(
    ("value", "expected"),
    [(512, 512), ("512 KB", 524288), ("1 MB", 1048576), ("32", 32), ("weird", None), (None, None)],
)
def test_size_parsing(value: object, expected: int | None) -> None:
    assert identity._size_bytes(value) == expected


# --- usage -----------------------------------------------------------------------

Freq = namedtuple("Freq", "current min max")
Times = namedtuple("Times", "user system idle interrupt dpc")
Stats = namedtuple("Stats", "ctx_switches interrupts soft_interrupts syscalls")


def _fake_psutil(**overrides: Any) -> SimpleNamespace:
    base = {
        "cpu_percent": lambda interval=None, percpu=False: [10.0, 20.0, 30.0, 40.0],
        "cpu_freq": lambda: Freq(2011.0, 0.0, 3301.0),
        "cpu_times": lambda: Times(100.5, 50.25, 900.0, 5.0, 4.0),
        "cpu_stats": lambda: Stats(1, 2, 3, 4),
        "getloadavg": lambda: (0.5, 0.25, 0.1),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_usage_from_fake_psutil(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _fake_psutil()
    monkeypatch.setattr(plat, "optional_import", lambda name: fake if name == "psutil" else None)
    problems = Problems()
    usage = collector.read_usage(problems, 0.5)
    assert isinstance(usage, CpuUsage)
    assert usage.percent == 25.0
    assert usage.per_core_percent == (10.0, 20.0, 30.0, 40.0)
    assert usage.frequency is not None
    assert usage.frequency.min_mhz is None  # psutil's 0.0 means unknown
    assert usage.frequency.max_mhz == 3301.0
    assert usage.times is not None
    assert usage.times.other_seconds == {"interrupt": 5.0, "dpc": 4.0}
    assert usage.stats is not None and usage.stats.syscalls == 4
    assert usage.load_average == (0.5, 0.25, 0.1)
    assert not problems


def test_usage_without_psutil(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plat, "optional_import", lambda name: None)
    problems = Problems()
    assert collector.read_usage(problems, 0.0) is None
    assert problems.freeze()[0].kind is ProblemKind.MISSING_DEPENDENCY


def test_usage_survives_partial_psutil_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken() -> None:
        raise OSError("sensor gone")

    fake = _fake_psutil(cpu_freq=broken, cpu_stats=broken)
    del fake.getloadavg
    monkeypatch.setattr(plat, "optional_import", lambda name: fake)
    problems = Problems()
    usage = collector.read_usage(problems, 0.0)
    assert usage is not None
    assert usage.frequency is None and usage.stats is None
    assert usage.times is not None
    assert usage.load_average is None
    kinds = {(p.source, p.kind) for p in problems.freeze()}
    assert ("psutil.cpu_freq", ProblemKind.BACKEND_ERROR) in kinds
    assert ("psutil.getloadavg", ProblemKind.UNSUPPORTED_PLATFORM) in kinds


def test_usage_none_when_sampling_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(**kw: object) -> None:
        raise RuntimeError("no counters")

    monkeypatch.setattr(plat, "optional_import", lambda name: _fake_psutil(cpu_percent=broken))
    problems = Problems()
    assert collector.read_usage(problems, 0.0) is None
    assert problems.freeze()[0].source == "psutil.cpu_percent"


# --- the public entry point ---------------------------------------------------------


def test_cpu_rejects_negative_sample() -> None:
    with pytest.raises(ValueError, match="negative"):
        mabat.cpu(sample_seconds=-1)


def test_cpu_zero_sample_does_not_block_and_serialises() -> None:
    section = mabat.cpu(sample_seconds=0)
    assert section.available
    assert section.data is not None and section.data.usage is not None
    assert section.data.usage.sample_seconds == 0.0
    payload = json.loads(mabat.to_json(section))
    assert payload["name"] == "cpu"
    assert set(payload["data"]) == {"identity", "usage"}
    assert payload["data"]["identity"]["logical_cores"] >= 1


def test_cpu_uses_settings_sample_window(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[float | None] = []

    def cpu_percent(interval: float | None = None, percpu: bool = False) -> list[float]:
        seen.append(interval)
        return [1.0]

    monkeypatch.setattr(plat, "optional_import", lambda name: _fake_psutil(cpu_percent=cpu_percent))
    monkeypatch.setattr(identity, "_cpuinfo_raw", lambda: (FULL_CPUINFO, None))
    Path(config.LOCAL_CONFIG_NAME).write_text("[sampling]\ncpu_sample_seconds = 0.25\n")
    config.settings.cache_clear()
    section = mabat.cpu()
    assert section.data is not None and section.data.usage is not None
    assert section.data.usage.sample_seconds == 0.25
    assert seen == [0.25]


def test_cpu_is_unavailable_only_when_nothing_at_all_is_readable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(plat, "optional_import", lambda name: None)

    def no_identity(problems: Problems) -> None:
        raise RuntimeError("identity exploded")

    monkeypatch.setattr(collector, "read_identity", no_identity)
    section = mabat.cpu(sample_seconds=0)
    assert not section.available
    assert {p.source for p in section.problems} == {"cpu.identity", "psutil"}
