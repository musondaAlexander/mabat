"""Sensor providers.

``read_psutil`` covers Linux (``/sys/class/hwmon`` through psutil). ``read_hardware_monitor``
covers Windows through the WMI namespace that LibreHardwareMonitor (or the older
OpenHardwareMonitor) publishes while it is running; there is no built-in Windows API for
CPU temperature. macOS has neither and is reported as unsupported by the collector.
"""

from __future__ import annotations

import json
import math
from typing import Any

from mabat._shared import platform as plat
from mabat._shared.models import ProblemKind, Problems
from mabat.sections.sensors.models import Fan, Power, SensorsReport, Temperature

LHM_URL = "https://github.com/LibreHardwareMonitor/LibreHardwareMonitor"
NOT_RUNNING_HINT = (
    "LibreHardwareMonitor is not running. Install it from "
    f"{LHM_URL}, start it (as Administrator for CPU sensors) and keep it open."
)

# One PowerShell launch tries both namespaces (they publish the same Hardware/Sensor
# schema) and reports which one answered. Fixed script; never built from user input.
_PROVIDERS = {
    r"root\LibreHardwareMonitor": "librehardwaremonitor",
    r"root\OpenHardwareMonitor": "openhardwaremonitor",
}
_QUERY = (
    "$out = $null; $err = $null; "
    r"foreach ($ns in @('root\LibreHardwareMonitor','root\OpenHardwareMonitor')) { "
    "try { "
    "$hw = @(Get-CimInstance -Namespace $ns -ClassName Hardware -ErrorAction Stop "
    "| Select-Object Identifier, Name, HardwareType); "
    "$se = @(Get-CimInstance -Namespace $ns -ClassName Sensor -ErrorAction Stop "
    "| Where-Object { $_.SensorType -in @('Temperature','Fan','Power') } "
    "| Select-Object Identifier, Name, SensorType, Value, Parent); "
    "$out = @{ namespace = $ns; hardware = $hw; sensors = $se }; break "
    "} catch { if ($_.Exception.Message -notmatch 'Invalid namespace') "
    "{ $err = $_.Exception.Message } } "
    "}; "
    "if ($null -eq $out) { @{ error = $err } | ConvertTo-Json -Compress } "
    "else { $out | ConvertTo-Json -Depth 4 -Compress }"
)


def _finite(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


# --- Linux: psutil ---------------------------------------------------------------------


def read_psutil(psutil: Any, problems: Problems) -> SensorsReport | None:
    temps_raw = psutil.sensors_temperatures() or {}
    fans_raw = psutil.sensors_fans() or {} if hasattr(psutil, "sensors_fans") else {}

    temperatures = tuple(
        Temperature(
            hardware=str(chip),
            label=str(entry.label or chip),
            celsius=float(entry.current),
            high_c=_finite(entry.high),
            critical_c=_finite(entry.critical),
        )
        for chip, entries in temps_raw.items()
        for entry in entries
        if _finite(entry.current) is not None
    )
    fans = tuple(
        Fan(hardware=str(chip), label=str(entry.label or chip), rpm=float(entry.current))
        for chip, entries in fans_raw.items()
        for entry in entries
        if _finite(entry.current) is not None
    )
    if not temperatures and not fans:
        problems.add(
            "psutil.sensors",
            ProblemKind.NOT_PRESENT,
            "no hardware sensors exposed (containers and virtual machines rarely have any)",
        )
        return None
    return SensorsReport(provider="psutil", temperatures=temperatures, fans=fans, powers=())


# --- Windows: LibreHardwareMonitor / OpenHardwareMonitor via WMI --------------------------------


def _rows(value: object) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [value]
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _parse(provider: str, payload: dict[str, Any]) -> SensorsReport:
    names = {
        str(row.get("Identifier")): str(row.get("Name") or row.get("Identifier"))
        for row in _rows(payload.get("hardware"))
    }
    temperatures: list[Temperature] = []
    fans: list[Fan] = []
    powers: list[Power] = []
    for row in _rows(payload.get("sensors")):
        value = _finite(row.get("Value"))
        if value is None:
            continue
        parent = str(row.get("Parent") or "")
        hardware = names.get(parent, parent or "unknown")
        label = str(row.get("Name") or row.get("Identifier") or "sensor")
        kind = str(row.get("SensorType") or "")
        if kind == "Temperature":
            temperatures.append(Temperature(hardware, label, value, None, None))
        elif kind == "Fan":
            fans.append(Fan(hardware, label, value))
        elif kind == "Power":
            powers.append(Power(hardware, label, value))
    return SensorsReport(
        provider=provider,
        temperatures=tuple(temperatures),
        fans=tuple(fans),
        powers=tuple(powers),
    )


def read_hardware_monitor(problems: Problems) -> SensorsReport | None:
    """Readings from whichever hardware-monitor WMI namespace answers."""
    if not plat.IS_WINDOWS:
        problems.add("hardware_monitor", ProblemKind.UNSUPPORTED_PLATFORM, "Windows only")
        return None
    try:
        result = plat.run_powershell(_QUERY)
        payload = json.loads(result.stdout or "null")
    except (plat.CommandError, NotImplementedError, json.JSONDecodeError) as exc:
        problems.add("hardware_monitor", ProblemKind.BACKEND_ERROR, f"{type(exc).__name__}: {exc}")
        return None
    if not isinstance(payload, dict) or "namespace" not in payload:
        error = payload.get("error") if isinstance(payload, dict) else None
        if error:
            problems.add("hardware_monitor", ProblemKind.BACKEND_ERROR, str(error))
        else:
            problems.add("hardware_monitor", ProblemKind.MISSING_DEPENDENCY, NOT_RUNNING_HINT)
        return None
    provider = _PROVIDERS.get(str(payload["namespace"]), "hardware_monitor")
    report = _parse(provider, payload)
    if not (report.temperatures or report.fans or report.powers):
        problems.add(provider, ProblemKind.NOT_PRESENT, "monitor is running but reports no sensors")
        return None
    return report
