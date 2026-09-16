"""Static CPU identity from py-cpuinfo, with psutil/platform fallbacks and a Windows WMI
fallback for the cache levels CPUID does not report there (see DECISIONS.md).

Identity never changes while the machine is up, so the expensive reads (py-cpuinfo spawns
a helper process; WMI takes ~0.3 s) are cached for the life of the process.
"""

from __future__ import annotations

import functools
import json
import os
import platform as _platform
import re
from collections.abc import Mapping
from typing import Any

from mabat._shared import platform as plat
from mabat._shared.models import ProblemKind, Problems, attempt
from mabat.sections.cpu.models import CpuCache, CpuIdentity

_SIZE_UNITS = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3}

# Fixed query; never built from user input (guard R6 keeps subprocess use in _shared).
_WMI_CACHE_QUERY = (
    "Get-CimInstance Win32_Processor | "
    "Select-Object L2CacheSize, L3CacheSize | ConvertTo-Json -Compress"
)


@functools.cache
def _cpuinfo_raw() -> tuple[Mapping[str, Any] | None, str | None]:
    """py-cpuinfo's dict, or ``(None, reason)``. Cached: it costs ~0.5 s per call."""
    module = plat.optional_import("cpuinfo")
    if module is None:
        return None, "py-cpuinfo is not installed (pip install py-cpuinfo)"
    try:
        return dict(module.get_cpu_info()), None
    except Exception as exc:  # broad on purpose: cached so the failure is paid once
        return None, f"{type(exc).__name__}: {exc}"


@functools.cache
def _wmi_cache_kib() -> tuple[Mapping[str, int | None] | None, str | None]:
    """``{"L2CacheSize": KiB, "L3CacheSize": KiB}`` from WMI on Windows, else ``(None, why)``."""
    if not plat.IS_WINDOWS:
        return None, "WMI cache fallback is Windows-only"
    try:
        result = plat.run_powershell(_WMI_CACHE_QUERY)
        parsed = json.loads(result.stdout or "null")
    except (plat.CommandError, NotImplementedError, json.JSONDecodeError) as exc:
        return None, f"{type(exc).__name__}: {exc}"
    if isinstance(parsed, list):  # multi-socket: take the first package
        parsed = parsed[0] if parsed else None
    if not isinstance(parsed, dict):
        return None, "Win32_Processor returned no rows"
    return {key: _as_int(parsed.get(key)) for key in ("L2CacheSize", "L3CacheSize")}, None


def clear_cache() -> None:
    """Forget cached identity reads (tests, or after a live CPU hot-plug)."""
    for cached in (_cpuinfo_raw, _wmi_cache_kib):
        clear = getattr(cached, "cache_clear", None)  # absent while a test has patched it
        if clear is not None:
            clear()


def _as_int(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return int(value)
    if isinstance(value, str):
        return int(value) if value.strip().isdigit() else None
    return None


def _size_bytes(value: object) -> int | None:
    """py-cpuinfo >= 9 gives bytes as int; older versions gave strings like '512 KB'."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return int(value)
    if isinstance(value, str):
        match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([KMG]?B)?\s*", value, re.IGNORECASE)
        if match:
            unit = (match.group(2) or "B").upper()
            return int(float(match.group(1)) * _SIZE_UNITS[unit])
    return None


def _bits_from_platform() -> int | None:
    match = re.match(r"(\d+)bit", _platform.architecture()[0])
    return int(match.group(1)) if match else None


def _core_counts(problems: Problems) -> tuple[int | None, int | None]:
    psutil = plat.optional_import("psutil")
    physical = logical = None
    if psutil is not None:
        physical = attempt(problems, "psutil.cpu_count", lambda: psutil.cpu_count(logical=False))
        logical = attempt(problems, "psutil.cpu_count", lambda: psutil.cpu_count(logical=True))
    return physical, logical if logical is not None else os.cpu_count()


def _cache(raw: Mapping[str, Any], problems: Problems) -> CpuCache:
    levels = {
        "l1_data_bytes": _size_bytes(raw.get("l1_data_cache_size")),
        "l1_instruction_bytes": _size_bytes(raw.get("l1_instruction_cache_size")),
        "l2_bytes": _size_bytes(raw.get("l2_cache_size")),
        "l3_bytes": _size_bytes(raw.get("l3_cache_size")),
    }
    if levels["l2_bytes"] is None or levels["l3_bytes"] is None:
        wmi, why = _wmi_cache_kib()
        if wmi is not None:
            for key, wmi_key in (("l2_bytes", "L2CacheSize"), ("l3_bytes", "L3CacheSize")):
                kib = wmi[wmi_key]
                if levels[key] is None and kib:
                    levels[key] = kib * 1024
        elif why and not why.endswith("Windows-only"):
            problems.add("wmi.Win32_Processor", ProblemKind.BACKEND_ERROR, why)
    missing = [name for name, size in levels.items() if size is None]
    if missing:
        problems.add(
            "cpuinfo.cache",
            ProblemKind.NOT_PRESENT,
            "cache size not reported by this platform: " + ", ".join(missing),
        )
    return CpuCache(**levels)


def read_identity(problems: Problems) -> CpuIdentity:
    """Best-effort identity: py-cpuinfo first, then psutil/platform for whatever is left."""
    raw, why = _cpuinfo_raw()
    if raw is None:
        problems.add("cpuinfo", ProblemKind.MISSING_DEPENDENCY, why or "unavailable")
        raw = {}
    physical, logical = _core_counts(problems)
    advertised = raw.get("hz_advertised")
    return CpuIdentity(
        brand=raw.get("brand_raw") or (_platform.processor() or None),
        vendor=raw.get("vendor_id_raw"),
        architecture=raw.get("arch") or (_platform.machine() or None),
        bits=_as_int(raw.get("bits")) or _bits_from_platform(),
        physical_cores=physical,
        logical_cores=logical,
        advertised_hz=_as_int(advertised[0]) if isinstance(advertised, list | tuple) else None,
        family=_as_int(raw.get("family")),
        model=_as_int(raw.get("model")),
        stepping=_as_int(raw.get("stepping")),
        cache=_cache(raw, problems),
        flags=tuple(str(flag) for flag in raw.get("flags", ())),
    )
