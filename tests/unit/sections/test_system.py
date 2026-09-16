from __future__ import annotations

import json
from collections import namedtuple
from types import SimpleNamespace
from typing import Any

import pytest

import mabat
from mabat._shared import platform as plat
from mabat._shared.models import ProblemKind, Problems
from mabat.sections.system import collector, processes

Battery = namedtuple("Battery", "percent secsleft power_plugged")
SUser = namedtuple("SUser", "name terminal host started pid")
Mem = namedtuple("Mem", "rss vms")
Virtual = namedtuple("Virtual", "total available percent used free")


class GoneError(Exception):
    pass


class DeniedError(Exception):
    pass


class FakeProcess:
    """Enough of psutil.Process for the sampler: per-attribute failures are configurable."""

    def __init__(
        self,
        pid: int,
        name: str,
        cpu: float,
        rss: int,
        *,
        fail: dict[str, type[Exception]] | None = None,
        username: str | None = "alex",
    ) -> None:
        self.pid = pid
        self._name = name
        self._cpu = cpu
        self._rss = rss
        self._fail = fail or {}
        self._username = username
        self.cpu_calls = 0

    def _maybe_fail(self, attr: str) -> None:
        if attr in self._fail:
            raise self._fail[attr]()

    def oneshot(self) -> Any:
        class _Ctx:
            def __enter__(self_inner) -> None:  # noqa: N805
                return None

            def __exit__(self_inner, *exc: object) -> None:  # noqa: N805
                return None

        return _Ctx()

    def cpu_percent(self, interval: float | None = None) -> float:
        self._maybe_fail("cpu_percent")
        self.cpu_calls += 1
        return self._cpu

    def memory_info(self) -> Mem:
        self._maybe_fail("memory_info")
        return Mem(self._rss, self._rss * 2)

    def name(self) -> str:
        return self._name

    def username(self) -> str | None:
        self._maybe_fail("username")
        return self._username

    def status(self) -> str:
        self._maybe_fail("status")
        return "running"

    def num_threads(self) -> int:
        return 4

    def create_time(self) -> float:
        return 1_700_000_000.0


def _fake_psutil(procs: list[FakeProcess], **overrides: Any) -> SimpleNamespace:
    base: dict[str, Any] = {
        "NoSuchProcess": GoneError,
        "AccessDenied": DeniedError,
        "cpu_count": lambda logical=True: 4,
        "virtual_memory": lambda: Virtual(1_000_000, 500_000, 50.0, 500_000, 500_000),
        "process_iter": lambda: iter(procs),
        "boot_time": lambda: 1_700_000_000.0,
        "users": lambda: [SUser("alex", None, "", 1_700_000_100.0, 42)],
        "sensors_battery": lambda: Battery(80.0, 3600, False),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_processes_rank_normalise_and_enrich_top_only() -> None:
    procs = [
        FakeProcess(1, "idle", 400.0, 10),
        FakeProcess(2, "busy", 200.0, 500),
        FakeProcess(3, "quiet", 4.0, 900),
        FakeProcess(4, "tiny", 4.0, 100),
    ]
    problems = Problems()
    top, total, inaccessible = processes.read_processes(
        _fake_psutil(procs), problems, 0.0, 2, lambda s: None, hidden_names={"idle"}
    )
    assert (total, inaccessible) == (4, 0)
    assert [p.name for p in top] == ["busy", "quiet"]  # idle hidden; cpu, then rss
    assert top[0].cpu_percent == 50.0  # 200 % of one core / 4 cores
    assert top[0].memory_percent == 0.05
    assert top[0].username == "alex" and top[0].status == "running"
    assert top[0].created is not None
    assert not problems


def test_processes_sample_primes_then_sleeps() -> None:
    procs = [FakeProcess(1, "a", 10.0, 1)]
    slept: list[float] = []
    processes.read_processes(_fake_psutil(procs), Problems(), 0.25, 5, slept.append)
    assert slept == [0.25]
    assert procs[0].cpu_calls == 2  # prime + measure


def test_processes_delta_mode_skips_priming() -> None:
    procs = [FakeProcess(1, "a", 10.0, 1)]
    slept: list[float] = []
    processes.read_processes(_fake_psutil(procs), Problems(), 0.0, 5, slept.append)
    assert slept == []
    assert procs[0].cpu_calls == 1


def test_processes_count_denied_and_skip_gone() -> None:
    procs = [
        FakeProcess(1, "ok", 1.0, 1),
        FakeProcess(2, "secret", 1.0, 1, fail={"cpu_percent": DeniedError}),
        FakeProcess(3, "exited", 1.0, 1, fail={"memory_info": GoneError}),
        FakeProcess(4, "half", 9.0, 1, fail={"username": DeniedError, "status": DeniedError}),
    ]
    problems = Problems()
    top, total, inaccessible = processes.read_processes(
        _fake_psutil(procs), problems, 0.0, 10, lambda s: None
    )
    assert (total, inaccessible) == (2, 1)
    assert [p.name for p in top] == ["half", "ok"]
    assert top[0].username is None and top[0].status == "unknown"
    assert problems.freeze()[0].kind is ProblemKind.PERMISSION_DENIED
    assert "1 processes" in problems.freeze()[0].detail


def test_os_identity_from_platform() -> None:
    problems = Problems()
    identity = collector.read_os(problems)
    assert identity.system and identity.hostname and identity.python
    if not plat.IS_LINUX:
        assert identity.distribution is None


def test_distribution_needs_distro_on_linux(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plat, "IS_LINUX", True)
    monkeypatch.setattr(plat, "optional_import", lambda name: None)
    problems = Problems()
    assert collector._distribution(problems) is None
    assert problems.freeze()[0].source == "distro"
    fake_distro = SimpleNamespace(name=lambda pretty=False: "Ubuntu 24.04 LTS")
    monkeypatch.setattr(plat, "optional_import", lambda name: fake_distro)
    assert collector._distribution(Problems()) == "Ubuntu 24.04 LTS"


def test_uptime_users_battery_from_fake_psutil() -> None:
    problems = Problems()
    fake = _fake_psutil([])
    uptime = collector.read_uptime(fake, problems)
    assert uptime is not None and uptime.uptime_seconds > 0
    assert uptime.boot_time.tzinfo is not None
    users = collector.read_users(fake, problems)
    assert users is not None and users[0].name == "alex" and users[0].host is None
    battery = collector.read_battery(fake, problems)
    assert battery is not None
    assert (battery.percent, battery.seconds_left, battery.power_plugged) == (80.0, 3600, False)
    assert not problems


def test_battery_absent_and_unsupported() -> None:
    problems = Problems()
    assert collector.read_battery(_fake_psutil([], sensors_battery=lambda: None), problems) is None
    assert problems.freeze()[0].kind is ProblemKind.NOT_PRESENT

    problems = Problems()
    no_api = _fake_psutil([])
    del no_api.sensors_battery
    assert collector.read_battery(no_api, problems) is None
    assert problems.freeze()[0].kind is ProblemKind.UNSUPPORTED_PLATFORM


def test_battery_unlimited_time_becomes_none() -> None:
    fake = _fake_psutil([], sensors_battery=lambda: Battery(100.0, -2, True))
    battery = collector.read_battery(fake, Problems())
    assert battery is not None and battery.seconds_left is None and battery.power_plugged


def test_system_without_psutil_keeps_os_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plat, "optional_import", lambda name: None)
    section = mabat.system()
    assert section.available
    assert section.data is not None and section.data.os is not None
    assert section.data.processes is None
    assert {p.source for p in section.problems} == {"psutil"}


def test_system_rejects_negative_arguments() -> None:
    with pytest.raises(ValueError, match="negative"):
        mabat.system(top_n=-1)
    with pytest.raises(ValueError, match="negative"):
        mabat.system(process_sample_seconds=-1)


def test_system_with_fake_psutil_end_to_end(monkeypatch: pytest.MonkeyPatch) -> None:
    procs = [FakeProcess(1, "a", 40.0, 10), FakeProcess(2, "b", 80.0, 20)]
    monkeypatch.setattr(plat, "optional_import", lambda name: _fake_psutil(procs))
    section = mabat.system(top_n=1, process_sample_seconds=0)
    assert section.available and section.data is not None
    summary = section.data.processes
    assert summary is not None
    assert summary.total == 2 and summary.top_n == 1
    assert [p.name for p in summary.top] == ["b"]


def test_system_on_this_machine_serialises() -> None:
    section = mabat.system(process_sample_seconds=0)
    assert section.available
    payload = json.loads(mabat.to_json(section))
    data = payload["data"]
    assert data["os"]["hostname"]
    assert data["uptime"]["uptime_seconds"] > 0
    assert data["processes"]["total"] > 0
    for proc in data["processes"]["top"]:
        assert set(proc) == {
            "pid",
            "name",
            "username",
            "status",
            "cpu_percent",
            "memory_percent",
            "memory_rss_bytes",
            "threads",
            "created",
        }
