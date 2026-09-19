from __future__ import annotations

import atexit
import ctypes
from datetime import UTC, datetime

import pytest
from rich.console import Console

from mabat._shared.config import settings
from mabat._shared.models import Problem, ProblemKind, Section
from mabat.cli.render import common


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, "-"), (0, "0 B"), (1023, "1023 B"), (1536, "1.5 KiB"), (16 * 2**20, "16.0 MiB")],
)
def test_fmt_bytes(value: int | None, expected: str) -> None:
    assert common.fmt_bytes(value) == expected


def test_fmt_bytes_precision_zero() -> None:
    assert common.fmt_bytes(16 * 2**20, precision=0) == "16 MiB"


@pytest.mark.parametrize(
    ("value", "mhz", "expected"),
    [
        (None, False, "-"),
        (3_294_000_000, False, "3.29 GHz"),
        (2011.0, True, "2.01 GHz"),
        (800.0, True, "800 MHz"),
    ],
)
def test_fmt_hz(value: float | None, mhz: bool, expected: str) -> None:
    assert common.fmt_hz(value, mhz=mhz) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, "-"), (59, "0m 59s"), (3_661, "1h 01m 01s"), (90_000, "1d 01h 00m")],
)
def test_fmt_seconds(value: float | None, expected: str) -> None:
    assert common.fmt_seconds(value) == expected


def test_pct_text_uses_thresholds() -> None:
    limits = settings().thresholds
    assert common.pct_text(limits.warn_percent - 1).style == "green"
    assert common.pct_text(limits.warn_percent).style == "yellow"
    assert common.pct_text(limits.critical_percent).style == "bold red"
    assert common.pct_text(None).plain == "-"


def test_bar_is_proportional_and_clamped() -> None:
    assert common.bar(50, width=10).plain == common.FILLED * 5 + common.EMPTY * 5
    assert common.bar(150, width=4).plain == common.FILLED * 4
    assert common.bar(-5, width=4).plain == common.EMPTY * 4


def test_problems_footer_lists_each_problem() -> None:
    section: Section[int] = Section(
        name="x",
        collected_at=datetime(2026, 1, 1, tzinfo=UTC),
        data=None,
        problems=(Problem("nvml", ProblemKind.MISSING_DEPENDENCY, "pip install [nvidia-ml-py]"),),
    )
    footer = common.problems_footer(section)
    assert footer is not None
    capture = Console(record=True, width=120, force_terminal=False)
    capture.print(footer)
    text = capture.export_text()
    assert "nvml [missing_dependency]" in text
    assert "pip install [nvidia-ml-py]" in text  # brackets survive: not parsed as markup


def test_problems_footer_is_none_without_problems() -> None:
    section: Section[int] = Section(name="x", collected_at=datetime(2026, 1, 1, tzinfo=UTC), data=1)
    assert common.problems_footer(section) is None


def test_assemble_skips_none() -> None:
    group = common.assemble(common.heading("a"), None, common.heading("b"))
    assert len(group.renderables) == 2


def _render_to_text(renderable: object) -> str:
    capture = Console(record=True, width=120, force_terminal=False)
    capture.print(renderable)
    return capture.export_text()


def test_render_system_handles_partial_reports() -> None:
    from mabat.cli.render.system import render_system
    from mabat.sections.system import Battery, OsIdentity, SystemReport

    report = SystemReport(
        os=OsIdentity("Linux", "6.8", "#1", "Linux-6.8", "x86_64", "box", "Ubuntu 24.04", "3.12"),
        uptime=None,
        users=(),
        battery=Battery(15.0, 900, False),
        processes=None,
    )
    section: Section[SystemReport] = Section(
        name="system", collected_at=datetime(2026, 1, 1, tzinfo=UTC), data=report
    )
    text = _render_to_text(render_system(section))
    assert "Ubuntu 24.04" in text
    assert "no logged-in users" in text
    assert "15 %" in text and "on battery" in text and "15m 00s left" in text


def test_render_storage_shows_smart_and_unknown_usage() -> None:
    from mabat.cli.render.storage import render_storage
    from mabat.sections.storage import Partition, SmartAttribute, SmartDevice, StorageReport

    report = StorageReport(
        partitions=(Partition("G:", "G:\\", "FAT32", "rw", None, None, None, None),),
        io=(),
        smart=(
            SmartDevice(
                "nvme0",
                "Fake [SSD]",
                "SN",
                "1.0",
                "nvme",
                10**12,
                "FAIL",
                70,
                tuple(SmartAttribute(i, f"attr{i}", 100, 100, 0, "0") for i in range(8)),
            ),
        ),
    )
    section: Section[StorageReport] = Section(
        name="storage", collected_at=datetime(2026, 1, 1, tzinfo=UTC), data=report
    )
    text = _render_to_text(render_storage(section))
    assert "G:\\" in text and "FAIL" in text and "Fake [SSD]" in text
    assert "no disk I/O counters" in text
    assert "+2 more attributes" in text


def test_render_unavailable_sections() -> None:
    from mabat.cli.render.storage import render_storage
    from mabat.cli.render.system import render_system

    when = datetime(2026, 1, 1, tzinfo=UTC)
    assert "unavailable" in _render_to_text(render_system(Section("system", when, None)))
    assert "unavailable" in _render_to_text(render_storage(Section("storage", when, None)))


def test_temp_text_uses_sensor_limit_or_settings() -> None:
    limits = settings().thresholds
    assert common.temp_text(limits.temperature_warn_c - 1).style == "green"
    assert common.temp_text(limits.temperature_warn_c).style == "yellow"
    assert common.temp_text(limits.temperature_critical_c).style == "bold red"
    assert common.temp_text(80, critical_c=100).style == "green"  # below 85 % of the limit
    assert common.temp_text(86, critical_c=100).style == "yellow"
    assert common.temp_text(100, critical_c=100).style == "bold red"
    assert common.temp_text(None).plain == "-"


def test_render_gpu_shows_telemetry_and_virtual_adapters() -> None:
    from mabat.cli.render.gpu import render_gpu
    from mabat.sections.gpu import GpuClocks, GpuDevice, GpuMemory, GpuReport, GpuTelemetry

    telemetry = GpuTelemetry(
        memory=GpuMemory(4096, 1024, 3072, 25.0),
        utilization_percent=42.0,
        memory_controller_percent=7.0,
        encoder_percent=3.0,
        decoder_percent=0.0,
        temperature_c=51,
        temperature_slowdown_c=97,
        power_watts=6.7,
        power_limit_watts=80.0,
        fan_percent=None,
        clocks=GpuClocks(210, 405, 2100),
        performance_state=8,
        pcie_generation=1,
        pcie_width=8,
        processes=2,
    )
    real = GpuDevice(
        "RTX [3050]",
        "NVIDIA",
        ("nvml",),
        True,
        "610.88",
        4096,
        "01:00.0",
        None,
        None,
        None,
        None,
        telemetry,
    )
    virtual = GpuDevice(
        "Parsec", "Parsec", ("wmi",), False, "0.45", None, None, None, None, None, None, None
    )
    section: Section[GpuReport] = Section(
        name="gpu",
        collected_at=datetime(2026, 1, 1, tzinfo=UTC),
        data=GpuReport((real, virtual), "610.88"),
    )
    text = _render_to_text(render_gpu(section))
    assert "RTX [3050]" in text and "(virtual adapter)" in text
    assert "42.0 %" in text and "1.0 KiB of 4.0 KiB" in text
    assert "51 C" in text and "slowdown at 97 C" in text
    assert (
        "6.7 W of 80 W" in text
        and "P8" in text
        and "PCIe gen1 x8" in text
        and "2 processes" in text
    )
    assert "fan" not in text  # unsupported reading is simply absent


def test_render_sensors_groups_readings() -> None:
    from mabat.cli.render.sensors import render_sensors
    from mabat.sections.sensors import Fan, Power, SensorsReport, Temperature

    report = SensorsReport(
        provider="librehardwaremonitor",
        temperatures=(
            Temperature("AMD Ryzen", "Tctl", 61.5, None, None),
            Temperature("nvme", "Composite", 45.0, 70.0, 85.0),
        ),
        fans=(Fan("GPU", "Fan #1", 1200.0),),
        powers=(Power("AMD Ryzen", "Package", 12.25),),
    )
    section: Section[SensorsReport] = Section(
        name="sensors", collected_at=datetime(2026, 1, 1, tzinfo=UTC), data=report
    )
    text = _render_to_text(render_sensors(section))
    assert "via librehardwaremonitor" in text
    assert "Temperatures" in text and "62 C" in text and "high 70, critical 85" in text
    assert "Fans" in text and "1200 rpm" in text
    assert ("Power" in text and "12.2 W" in text) or "12.3 W" in text


def test_render_network_hides_flagged_interfaces_and_shows_rates() -> None:
    from mabat.cli.render.network import fmt_rate, render_network
    from mabat.sections.network import Address, Counters, Interface, NetworkReport, Rates

    counters = Counters(1000, 2000, 1, 2, 0, 0, 0, 0)
    eth = Interface(
        "eth0",
        True,
        1000,
        1500,
        "full",
        False,
        (Address("ipv4", "192.168.1.10", "255.255.255.0", None),),
        counters,
        Rates(1536.0, 1024.0 * 1024, 1.0),
    )
    lo = Interface("lo", True, None, None, None, True, (), counters, None)
    report = NetworkReport("box", "192.168.1.10", (eth, lo), counters, None, None)
    section: Section[NetworkReport] = Section(
        name="network", collected_at=datetime(2026, 1, 1, tzinfo=UTC), data=report
    )
    text = _render_to_text(render_network(section))
    assert "eth0" in text and "192.168.1.10" in text
    assert "1.5 KiB/s" in text and "1.0 MiB/s" in text
    assert "1 hidden: lo" in text
    assert fmt_rate(None) == "-"


def test_render_connections_caps_rows() -> None:
    from mabat.cli.render.network import render_connections
    from mabat.sections.network import Connection, ConnectionsReport

    rows = tuple(
        Connection("ipv4", "tcp", "10.0.0.2", 40000 + i, "1.1.1.1", 443, "ESTABLISHED", 1, "app")
        for i in range(45)
    )
    report = ConnectionsReport(rows, {"ESTABLISHED": 45}, 0, 45)
    section: Section[ConnectionsReport] = Section(
        name="connections", collected_at=datetime(2026, 1, 1, tzinfo=UTC), data=report
    )
    text = _render_to_text(render_connections(section))
    assert "45 sockets" in text and "+5 more" in text


def test_render_snapshot_status_and_summaries() -> None:
    from mabat._shared.models import Problem, ProblemKind
    from mabat._snapshot import Snapshot
    from mabat.cli.render.snapshot import render_snapshot
    from mabat.sections.memory import MemoryReport, SwapMemory, VirtualMemory

    when = datetime(2026, 1, 1, tzinfo=UTC)
    memory = MemoryReport(
        VirtualMemory(4 * 2**30, 2**30, 3 * 2**30, 2**30, 75.0, {}),
        SwapMemory(2**30, 0, 2**30, 0.0, 0, 0),
    )
    skipped = Problem("x", ProblemKind.SKIPPED, "not collected: skipped by request")
    missing = Problem("nvml", ProblemKind.MISSING_DEPENDENCY, "pip install nvidia-ml-py. More.")
    partial = Problem("cpuinfo.cache", ProblemKind.NOT_PRESENT, "l1 unknown")
    snap = Snapshot(
        collected_at=when,
        hostname="box",
        platform="linux",
        cpu=Section("cpu", when, None, (partial,)),
        memory=Section("memory", when, memory),
        system=Section("system", when, None, (skipped,)),
        storage=Section("storage", when, None, (skipped,)),
        gpu=Section("gpu", when, None, (missing,)),
        sensors=Section("sensors", when, None, (skipped,)),
        network=Section("network", when, None, (skipped,)),
    )
    text = _render_to_text(render_snapshot(snap))
    assert "box" in text and "linux" in text
    assert "RAM 75.0 % (3.0 GiB of 4.0 GiB)" in text
    assert "unavailable" in text and "pip install nvidia-ml-py" in text
    assert "More." not in text  # only the first sentence of a reason
    assert text.count("skipped") >= 4


# --- Windows console: virtual-terminal processing -----------------------------------------


def _fake_kernel32(monkeypatch: pytest.MonkeyPatch, mode: int | None) -> list[int]:
    """Stand in for ``ctypes.WinDLL('kernel32')``; ``mode=None`` means stdout is no console.
    Returns the list of modes handed to ``SetConsoleMode``."""
    set_modes: list[int] = []

    class Kernel32:
        def __init__(self, name: str, use_last_error: bool = False) -> None:
            self.GetStdHandle = lambda which: 7  # Win32 spelling, as ctypes sees it
            self.GetConsoleMode = self._get_mode
            self.SetConsoleMode = self._set_mode

        @staticmethod
        def _get_mode(handle: int, out: object) -> int:
            if mode is None:
                return 0
            out._obj.value = mode  # type: ignore[attr-defined]  # ctypes.byref() argument
            return 1

        @staticmethod
        def _set_mode(handle: int, new_mode: int) -> int:
            set_modes.append(new_mode)
            return 1

    monkeypatch.setattr(ctypes, "WinDLL", Kernel32, raising=False)
    monkeypatch.setattr(atexit, "register", lambda *args: None)
    return set_modes


def test_vt_processing_is_switched_on_when_the_console_lacks_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_modes = _fake_kernel32(monkeypatch, mode=0x0003)
    assert common.enable_vt_processing() is True
    assert set_modes == [0x0003 | common._ENABLE_VIRTUAL_TERMINAL_PROCESSING]


def test_vt_processing_is_left_alone_when_already_on(monkeypatch: pytest.MonkeyPatch) -> None:
    set_modes = _fake_kernel32(monkeypatch, mode=0x0007)
    assert common.enable_vt_processing() is True
    assert set_modes == []


def test_vt_processing_is_a_no_op_off_a_console(monkeypatch: pytest.MonkeyPatch) -> None:
    set_modes = _fake_kernel32(monkeypatch, mode=None)
    assert common.enable_vt_processing() is False
    assert set_modes == []


def test_vt_processing_is_a_no_op_off_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delattr(ctypes, "WinDLL", raising=False)
    assert common.enable_vt_processing() is False
