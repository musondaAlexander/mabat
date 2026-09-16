"""Static adapter identity from WMI ``Win32_VideoController`` (Windows only).

This is what makes non-NVIDIA adapters (an AMD or Intel iGPU) visible at all on Windows;
it carries no live telemetry. ``AdapterRAM`` is a 32-bit field and saturates at 4 GiB.
The PowerShell round-trip costs ~1 s and adapters do not change while the machine is up,
so the rows are cached for the life of the process.
"""

from __future__ import annotations

import functools
import json
from typing import Any

from mabat._shared import platform as plat
from mabat._shared.models import ProblemKind, Problems
from mabat.sections.gpu.models import GpuDevice, GpuDisplay

SOURCE = "wmi.Win32_VideoController"

# Fixed query; never built from user input.
_QUERY = (
    "Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion, AdapterRAM, "
    "VideoProcessor, AdapterCompatibility, CurrentHorizontalResolution, "
    "CurrentVerticalResolution, CurrentRefreshRate, PNPDeviceID | ConvertTo-Json -Compress"
)


def _int(value: object) -> int | None:
    return int(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def _display(row: dict[str, Any]) -> GpuDisplay | None:
    width = _int(row.get("CurrentHorizontalResolution"))
    height = _int(row.get("CurrentVerticalResolution"))
    if not width or not height:
        return None
    return GpuDisplay(width=width, height=height, refresh_hz=_int(row.get("CurrentRefreshRate")))


def _device(row: dict[str, Any]) -> GpuDevice:
    pnp = str(row.get("PNPDeviceID") or "")
    return GpuDevice(
        name=str(row.get("Name") or "Unknown adapter"),
        vendor=row.get("AdapterCompatibility") or None,
        sources=(SOURCE,),
        physical=pnp.upper().startswith("PCI\\"),
        driver_version=row.get("DriverVersion") or None,
        memory_total_bytes=_int(row.get("AdapterRAM")),
        bus_id=pnp or None,
        uuid=None,
        vbios=None,
        processor=row.get("VideoProcessor") or None,
        display=_display(row),
        telemetry=None,
    )


@functools.cache
def _rows() -> tuple[tuple[GpuDevice, ...] | None, str | None]:
    """(adapters, error). Cached: see module docstring."""
    try:
        result = plat.run_powershell(_QUERY)
        parsed = json.loads(result.stdout or "null")
    except (plat.CommandError, NotImplementedError, json.JSONDecodeError) as exc:
        return None, f"{type(exc).__name__}: {exc}"
    if isinstance(parsed, dict):
        parsed = [parsed]
    if not isinstance(parsed, list):
        return (), "Win32_VideoController returned no rows"
    return tuple(_device(row) for row in parsed if isinstance(row, dict)), None


def clear_cache() -> None:
    clear = getattr(_rows, "cache_clear", None)
    if clear is not None:
        clear()


def read_wmi(problems: Problems) -> tuple[GpuDevice, ...] | None:
    """Adapters known to Windows, or ``None`` (with a problem) when WMI is unusable."""
    if not plat.IS_WINDOWS:
        return None
    devices, error = _rows()
    if error:
        kind = ProblemKind.NOT_PRESENT if devices == () else ProblemKind.BACKEND_ERROR
        problems.add(SOURCE, kind, error)
    return devices
