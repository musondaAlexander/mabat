"""S.M.A.R.T. health via pySMART (which drives the ``smartctl`` binary from smartmontools).

Needs smartmontools installed and, on Windows and most Linux setups, an elevated shell -
smartctl issues raw ATA/NVMe passthrough commands. Every one of those preconditions is
reported as a distinct problem kind so a UI can tell the user exactly what to do.
"""

from __future__ import annotations

import logging
from typing import Any

from mabat._shared import platform as plat
from mabat._shared.models import ProblemKind, Problems
from mabat.sections.storage.models import SmartAttribute, SmartDevice

INSTALL_HINT = "install smartmontools (https://www.smartmontools.org) so 'smartctl' is on PATH"


def _int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return int(value)
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value)
    return None


def _attributes(device: Any) -> tuple[SmartAttribute, ...]:
    found: list[SmartAttribute] = []
    for attr in getattr(device, "attributes", None) or ():
        if attr is None:
            continue
        found.append(
            SmartAttribute(
                id=_int(getattr(attr, "num", None)),
                name=str(getattr(attr, "name", "") or "unknown"),
                value=_int(getattr(attr, "value", None)),
                worst=_int(getattr(attr, "worst", None)),
                threshold=_int(getattr(attr, "thresh", None)),
                raw=str(getattr(attr, "raw", "") or ""),
            )
        )
    return tuple(found)


def _device(device: Any) -> SmartDevice:
    return SmartDevice(
        name=str(device.name),
        model=getattr(device, "model", None) or None,
        serial=getattr(device, "serial", None) or None,
        firmware=getattr(device, "firmware", None) or None,
        interface=getattr(device, "interface", None) or None,
        capacity_bytes=_int(getattr(device, "size", None)),
        assessment=getattr(device, "assessment", None) or None,
        temperature_c=_int(getattr(device, "temperature", None)),
        attributes=_attributes(device),
    )


def read_smart(problems: Problems) -> tuple[SmartDevice, ...] | None:
    """SMART devices, or ``None`` with a problem explaining which precondition failed."""
    if not plat.command_available("smartctl"):
        problems.add("smartctl", ProblemKind.MISSING_DEPENDENCY, INSTALL_HINT)
        return None
    pysmart = plat.optional_import("pySMART")
    if pysmart is None:
        problems.add("pySMART", ProblemKind.MISSING_DEPENDENCY, "pip install pySMART")
        return None

    # pySMART logs every smartctl hiccup at WARNING; those become our problems instead.
    logging.getLogger("pySMART").setLevel(logging.ERROR)
    try:
        devices = list(pysmart.DeviceList().devices)
    except FileNotFoundError as exc:
        problems.add("smartctl", ProblemKind.MISSING_DEPENDENCY, f"{exc}; {INSTALL_HINT}")
        return None
    except PermissionError as exc:
        problems.add("smartctl", ProblemKind.PERMISSION_DENIED, str(exc))
        return None

    if not devices:
        kind = ProblemKind.NOT_PRESENT if plat.is_admin() else ProblemKind.PERMISSION_DENIED
        detail = (
            "smartctl found no SMART-capable devices"
            if kind is ProblemKind.NOT_PRESENT
            else "smartctl found no devices; SMART needs an elevated (Administrator/root) shell"
        )
        problems.add("smartctl", kind, detail)
        return ()
    return tuple(_device(device) for device in devices)
