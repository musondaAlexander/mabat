from __future__ import annotations

import json
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest

import mabat
from mabat._shared import platform as plat
from mabat._shared.models import ProblemKind, Problems
from mabat.sections.gpu import collector, nvml, wmi
from mabat.sections.gpu.models import GpuDevice, GpuDisplay

NOT_SUPPORTED = 3


class NVMLError(Exception):
    def __init__(self, value: int) -> None:
        super().__init__(f"nvml error {value}")
        self.value = value


def _fake_pynvml(
    *, count: int = 1, unsupported: set[str] | None = None, init_fails: bool = False
) -> SimpleNamespace:
    unsupported = unsupported or set()

    def maybe(name: str, value: Any) -> Any:
        if name in unsupported:
            raise NVMLError(NOT_SUPPORTED)
        return value

    def init() -> None:
        if init_fails:
            raise NVMLError(9)

    return SimpleNamespace(
        NVMLError=NVMLError,
        NVML_ERROR_NOT_SUPPORTED=NOT_SUPPORTED,
        NVML_TEMPERATURE_GPU=0,
        NVML_TEMPERATURE_THRESHOLD_SLOWDOWN=0,
        NVML_CLOCK_GRAPHICS=0,
        NVML_CLOCK_MEM=1,
        nvmlInit=init,
        nvmlShutdown=lambda: None,
        nvmlSystemGetDriverVersion=lambda: b"610.88",
        nvmlDeviceGetCount=lambda: count,
        nvmlDeviceGetHandleByIndex=lambda i: f"handle{i}",
        nvmlDeviceGetName=lambda h: "NVIDIA GeForce RTX 3050 Laptop GPU",
        nvmlDeviceGetUUID=lambda h: "GPU-abc",
        nvmlDeviceGetPciInfo=lambda h: SimpleNamespace(busId=b"00000000:01:00.0"),
        nvmlDeviceGetVbiosVersion=lambda h: "94.07",
        nvmlDeviceGetMemoryInfo=lambda h: maybe(
            "memory", SimpleNamespace(total=4096, used=1024, free=3072)
        ),
        nvmlDeviceGetUtilizationRates=lambda h: SimpleNamespace(gpu=42, memory=7),
        nvmlDeviceGetEncoderUtilization=lambda h: [3, 100000],
        nvmlDeviceGetDecoderUtilization=lambda h: [0, 100000],
        nvmlDeviceGetTemperature=lambda h, kind: 51,
        nvmlDeviceGetTemperatureThreshold=lambda h, kind: 97,
        nvmlDeviceGetPowerUsage=lambda h: 6716,
        nvmlDeviceGetEnforcedPowerLimit=lambda h: 80000,
        nvmlDeviceGetFanSpeed=lambda h: maybe("fan", 35),
        nvmlDeviceGetClockInfo=lambda h, kind: 210 if kind == 0 else 405,
        nvmlDeviceGetMaxClockInfo=lambda h, kind: 2100,
        nvmlDeviceGetPerformanceState=lambda h: 8,
        nvmlDeviceGetCurrPcieLinkGeneration=lambda h: 1,
        nvmlDeviceGetCurrPcieLinkWidth=lambda h: 8,
        nvmlDeviceGetGraphicsRunningProcesses=lambda h: [],
        nvmlDeviceGetComputeRunningProcesses=lambda h: [object()],
    )


WMI_ROWS = [
    {
        "Name": "NVIDIA GeForce RTX 3050 Laptop GPU",
        "DriverVersion": "32.0",
        "AdapterRAM": 4293918720,
        "PNPDeviceID": r"PCI\VEN_10DE",
        "CurrentHorizontalResolution": None,
    },
    {
        "Name": "AMD Radeon(TM) Graphics",
        "DriverVersion": "31.0",
        "AdapterRAM": 536870912,
        "VideoProcessor": "AMD Radeon Graphics Processor (0x1638)",
        "AdapterCompatibility": "Advanced Micro Devices, Inc.",
        "PNPDeviceID": r"PCI\VEN_1002",
        "CurrentHorizontalResolution": 1920,
        "CurrentVerticalResolution": 1080,
        "CurrentRefreshRate": 120,
    },
    {
        "Name": "Parsec Virtual Display Adapter",
        "DriverVersion": "0.45",
        "AdapterRAM": None,
        "PNPDeviceID": "ROOT\\DISPLAY\0000",
    },
]


def _powershell(stdout: str) -> Any:
    return lambda script, **kw: plat.CommandResult(("powershell",), 0, stdout, "")


@pytest.fixture(autouse=True)
def _no_wmi_cache() -> Iterator[None]:
    wmi.clear_cache()
    yield
    wmi.clear_cache()


# --- NVML -------------------------------------------------------------------------


def test_nvml_reads_every_field(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plat, "optional_import", lambda name: _fake_pynvml())
    problems = Problems()
    result = nvml.read_nvml(problems)
    assert result is not None
    devices, driver = result
    assert driver == "610.88" and len(devices) == 1
    dev = devices[0]
    assert dev.name.startswith("NVIDIA") and dev.driver_version == "610.88" and dev.physical
    assert dev.bus_id == "00000000:01:00.0" and dev.memory_total_bytes == 4096
    t = dev.telemetry
    assert t is not None and t.memory is not None
    assert (t.memory.used_bytes, t.memory.percent) == (1024, 25.0)
    assert (t.utilization_percent, t.memory_controller_percent) == (42.0, 7.0)
    assert (t.encoder_percent, t.decoder_percent) == (3.0, 0.0)
    assert (t.temperature_c, t.temperature_slowdown_c) == (51, 97)
    assert (t.power_watts, t.power_limit_watts) == (6.7, 80.0)
    assert t.fan_percent == 35 and t.processes == 1 and t.performance_state == 8
    assert t.clocks is not None and t.clocks.graphics_max_mhz == 2100
    assert (t.pcie_generation, t.pcie_width) == (1, 8)
    assert not problems


def test_nvml_unsupported_readings_are_one_problem(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        plat, "optional_import", lambda name: _fake_pynvml(unsupported={"fan", "memory"})
    )
    problems = Problems()
    result = nvml.read_nvml(problems)
    assert result is not None
    dev = result[0][0]
    assert dev.telemetry is not None and dev.telemetry.fan_percent is None
    assert dev.telemetry.memory is None and dev.memory_total_bytes is None
    assert len(problems) == 1
    problem = problems.freeze()[0]
    assert (
        problem.kind is ProblemKind.NOT_PRESENT
        and "fan" in problem.detail
        and "memory" in problem.detail
    )


def test_nvml_missing_and_failing_init(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plat, "optional_import", lambda name: None)
    problems = Problems()
    assert nvml.read_nvml(problems) is None
    assert problems.freeze()[0].kind is ProblemKind.MISSING_DEPENDENCY

    monkeypatch.setattr(plat, "optional_import", lambda name: _fake_pynvml(init_fails=True))
    problems = Problems()
    assert nvml.read_nvml(problems) is None
    assert problems.freeze()[0].kind is ProblemKind.NOT_PRESENT


# --- WMI --------------------------------------------------------------------------


def test_wmi_rows_become_devices(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plat, "IS_WINDOWS", True)
    monkeypatch.setattr(plat, "run_powershell", _powershell(json.dumps(WMI_ROWS)))
    problems = Problems()
    devices = wmi.read_wmi(problems)
    assert devices is not None and [d.name for d in devices][1] == "AMD Radeon(TM) Graphics"
    radeon = devices[1]
    assert radeon.physical and radeon.vendor == "Advanced Micro Devices, Inc."
    assert radeon.display is not None and (radeon.display.width, radeon.display.refresh_hz) == (
        1920,
        120,
    )
    assert radeon.processor and radeon.memory_total_bytes == 536870912
    parsec = devices[2]
    assert not parsec.physical and parsec.memory_total_bytes is None and parsec.display is None
    assert not problems


def test_wmi_single_row_and_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plat, "IS_WINDOWS", True)
    monkeypatch.setattr(plat, "run_powershell", _powershell(json.dumps(WMI_ROWS[1])))
    devices = wmi.read_wmi(Problems())
    assert devices is not None and len(devices) == 1
    wmi.clear_cache()

    def failing(script: str, **kw: object) -> None:
        raise plat.CommandFailedError("boom", plat.CommandResult(("powershell",), 1, "", "boom"))

    monkeypatch.setattr(plat, "run_powershell", failing)
    problems = Problems()
    assert wmi.read_wmi(problems) is None
    assert problems.freeze()[0].kind is ProblemKind.BACKEND_ERROR


def test_wmi_is_skipped_off_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plat, "IS_WINDOWS", False)
    calls: list[str] = []
    monkeypatch.setattr(plat, "run_powershell", lambda script, **kw: calls.append(script))
    problems = Problems()
    assert wmi.read_wmi(problems) is None
    assert calls == [] and not problems


def test_wmi_rows_are_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plat, "IS_WINDOWS", True)
    calls: list[str] = []

    def once(script: str, **kw: object) -> plat.CommandResult:
        calls.append(script)
        return plat.CommandResult(("powershell",), 0, json.dumps(WMI_ROWS), "")

    monkeypatch.setattr(plat, "run_powershell", once)
    wmi.read_wmi(Problems())
    wmi.read_wmi(Problems())
    assert len(calls) == 1


# --- merge + entry point ----------------------------------------------------------------


def _device(name: str, *, physical: bool = True, display: Any = None) -> GpuDevice:
    return GpuDevice(
        name, None, ("wmi",), physical, None, None, None, None, None, None, display, None
    )


def test_merge_enriches_matching_adapter_and_orders_the_rest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(plat, "optional_import", lambda name: _fake_pynvml())
    nvml_devices, _ = nvml.read_nvml(Problems()) or ((), None)
    wmi_devices = (
        _device("Parsec Virtual Display Adapter", physical=False),
        _device("nvidia geforce rtx 3050 laptop gpu ", display=GpuDisplay(1920, 1080, 120)),
        _device("AMD Radeon(TM) Graphics"),
    )
    merged = collector.merge(nvml_devices, wmi_devices)
    assert [d.name for d in merged] == [
        "NVIDIA GeForce RTX 3050 Laptop GPU",
        "AMD Radeon(TM) Graphics",
        "Parsec Virtual Display Adapter",
    ]
    assert merged[0].sources == ("nvml", "wmi") and merged[0].display == GpuDisplay(1920, 1080, 120)
    assert merged[0].telemetry is not None  # NVML data kept


def test_gpu_no_adapters_at_all(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plat, "optional_import", lambda name: _fake_pynvml(count=0))
    monkeypatch.setattr(plat, "IS_WINDOWS", False)
    section = mabat.gpu()
    assert not section.available
    assert any(
        p.kind is ProblemKind.NOT_PRESENT and "no NVIDIA GPU" in p.detail for p in section.problems
    )


def test_gpu_without_pynvml_still_lists_wmi_adapters(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plat, "optional_import", lambda name: None)
    monkeypatch.setattr(plat, "IS_WINDOWS", True)
    monkeypatch.setattr(plat, "run_powershell", _powershell(json.dumps(WMI_ROWS)))
    section = mabat.gpu()
    assert section.available and section.data is not None
    assert len(section.data.devices) == 3 and section.data.nvml_driver_version is None
    assert section.data.devices[0].telemetry is None
    assert section.problems[0].source == "nvml"


def test_gpu_on_this_machine_serialises() -> None:
    section = mabat.gpu()
    payload = json.loads(mabat.to_json(section))
    assert payload["name"] == "gpu"
    if payload["available"]:
        for device in payload["data"]["devices"]:
            assert {"name", "physical", "sources", "telemetry"} <= set(device)
