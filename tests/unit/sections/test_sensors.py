from __future__ import annotations

import json
import math
from collections import namedtuple
from types import SimpleNamespace
from typing import Any

import pytest

import mabat
from mabat._shared import platform as plat
from mabat._shared.models import ProblemKind, Problems
from mabat.sections.sensors import providers

Temp = namedtuple("Temp", "label current high critical")
FanT = namedtuple("FanT", "label current")

LHM_PAYLOAD = {
    "namespace": r"root\LibreHardwareMonitor",
    "hardware": [
        {"Identifier": "/amdcpu/0", "Name": "AMD Ryzen 5 5600H", "HardwareType": "Cpu"},
        {
            "Identifier": "/gpu-nvidia/0",
            "Name": "NVIDIA GeForce RTX 3050",
            "HardwareType": "GpuNvidia",
        },
    ],
    "sensors": [
        {
            "Identifier": "/amdcpu/0/temperature/2",
            "Name": "Core (Tctl/Tdie)",
            "SensorType": "Temperature",
            "Value": 61.5,
            "Parent": "/amdcpu/0",
        },
        {
            "Identifier": "/gpu-nvidia/0/temperature/0",
            "Name": "GPU Core",
            "SensorType": "Temperature",
            "Value": 47.0,
            "Parent": "/gpu-nvidia/0",
        },
        {
            "Identifier": "/gpu-nvidia/0/fan/0",
            "Name": "GPU Fan",
            "SensorType": "Fan",
            "Value": 0.0,
            "Parent": "/gpu-nvidia/0",
        },
        {
            "Identifier": "/amdcpu/0/power/0",
            "Name": "Package",
            "SensorType": "Power",
            "Value": 12.25,
            "Parent": "/amdcpu/0",
        },
        {
            "Identifier": "/amdcpu/0/temperature/9",
            "Name": "Broken",
            "SensorType": "Temperature",
            "Value": None,
            "Parent": "/amdcpu/0",
        },
        {
            "Identifier": "/mb/0/temperature/0",
            "Name": "Orphan",
            "SensorType": "Temperature",
            "Value": 30.0,
            "Parent": "/mb/0",
        },
    ],
}


def _powershell(stdout: str) -> Any:
    return lambda script, **kw: plat.CommandResult(("powershell",), 0, stdout, "")


# --- psutil (Linux) ---------------------------------------------------------------------


def test_psutil_provider_maps_temperatures_and_fans() -> None:
    fake = SimpleNamespace(
        sensors_temperatures=lambda: {
            "coretemp": [Temp("Package id 0", 55.0, 80.0, 100.0), Temp("", 52.0, None, None)],
            "nvme": [Temp("Composite", math.nan, None, None)],
        },
        sensors_fans=lambda: {"thinkpad": [FanT("", 2800)]},
    )
    problems = Problems()
    report = providers.read_psutil(fake, problems)
    assert report is not None and report.provider == "psutil"
    assert [t.label for t in report.temperatures] == ["Package id 0", "coretemp"]  # NaN dropped
    assert report.temperatures[0].critical_c == 100.0 and report.temperatures[1].high_c is None
    assert report.fans[0].rpm == 2800.0 and report.fans[0].label == "thinkpad"
    assert report.powers == () and not problems


def test_psutil_provider_with_nothing_exposed() -> None:
    fake = SimpleNamespace(sensors_temperatures=lambda: {}, sensors_fans=lambda: {})
    problems = Problems()
    assert providers.read_psutil(fake, problems) is None
    assert problems.freeze()[0].kind is ProblemKind.NOT_PRESENT


# --- LibreHardwareMonitor (Windows) ---------------------------------------------------------


def test_hardware_monitor_parses_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plat, "IS_WINDOWS", True)
    monkeypatch.setattr(plat, "run_powershell", _powershell(json.dumps(LHM_PAYLOAD)))
    problems = Problems()
    report = providers.read_hardware_monitor(problems)
    assert report is not None and report.provider == "librehardwaremonitor"
    temps = {t.label: t for t in report.temperatures}
    assert temps["Core (Tctl/Tdie)"].hardware == "AMD Ryzen 5 5600H"
    assert temps["Core (Tctl/Tdie)"].celsius == 61.5
    assert "Broken" not in temps  # null value skipped
    assert temps["Orphan"].hardware == "/mb/0"  # unknown parent keeps the identifier
    assert report.fans[0].rpm == 0.0
    assert report.powers[0].watts == 12.25
    assert not problems


def test_hardware_monitor_not_running(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plat, "IS_WINDOWS", True)
    monkeypatch.setattr(plat, "run_powershell", _powershell('{"error":null}'))
    problems = Problems()
    assert providers.read_hardware_monitor(problems) is None
    problem = problems.freeze()[0]
    assert (
        problem.kind is ProblemKind.MISSING_DEPENDENCY and "LibreHardwareMonitor" in problem.detail
    )


def test_hardware_monitor_wmi_error_and_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plat, "IS_WINDOWS", True)
    monkeypatch.setattr(plat, "run_powershell", _powershell('{"error":"Access denied"}'))
    problems = Problems()
    assert providers.read_hardware_monitor(problems) is None
    assert problems.freeze()[0].kind is ProblemKind.BACKEND_ERROR

    empty = {"namespace": r"root\OpenHardwareMonitor", "hardware": [], "sensors": []}
    monkeypatch.setattr(plat, "run_powershell", _powershell(json.dumps(empty)))
    problems = Problems()
    assert providers.read_hardware_monitor(problems) is None
    assert problems.freeze()[0].source == "openhardwaremonitor"
    assert problems.freeze()[0].kind is ProblemKind.NOT_PRESENT


def test_hardware_monitor_powershell_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(script: str, **kw: object) -> None:
        raise plat.CommandNotFoundError("'powershell' is not installed or not on PATH")

    monkeypatch.setattr(plat, "IS_WINDOWS", True)
    monkeypatch.setattr(plat, "run_powershell", missing)
    problems = Problems()
    assert providers.read_hardware_monitor(problems) is None
    assert problems.freeze()[0].kind is ProblemKind.BACKEND_ERROR


# --- entry point ---------------------------------------------------------------------------


def test_sensors_prefers_psutil_when_it_has_sensors(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = SimpleNamespace(
        sensors_temperatures=lambda: {"chip": [Temp("t", 40.0, None, None)]},
        sensors_fans=lambda: {},
    )
    monkeypatch.setattr(plat, "optional_import", lambda name: fake)
    section = mabat.sensors()
    assert section.available and section.data is not None and section.data.provider == "psutil"


def test_sensors_unsupported_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plat, "optional_import", lambda name: SimpleNamespace())  # no sensors_*
    monkeypatch.setattr(plat, "IS_WINDOWS", False)
    monkeypatch.setattr(plat, "IS_MACOS", True)
    section = mabat.sensors()
    assert not section.available
    assert section.problems[0].kind is ProblemKind.UNSUPPORTED_PLATFORM
    assert "macOS" in section.problems[0].detail


def test_sensors_on_this_machine_serialises() -> None:
    section = mabat.sensors()
    payload = json.loads(mabat.to_json(section))
    assert payload["name"] == "sensors"
    assert payload["available"] == (payload["data"] is not None)
