"""Live load and memory for *any* adapter on Windows via GPU performance counters.

This is what Task Manager's GPU tab reads. ``GPU Engine(*)\\Utilization Percentage`` has
one instance per process x adapter x engine; summing per engine type and taking the
busiest type gives Task Manager's headline figure. ``GPU Adapter Memory(*)`` gives
dedicated/shared usage per adapter. Adapters are identified by LUID; the
``HKLM\\SOFTWARE\\Microsoft\\DirectX`` registry maps LUIDs to names and dedicated totals.

Rate counters need two samples a second apart, so one call costs ~3-5 s. Opt in with
``gpu(counters=True)`` or ``[gpu] counters = true``; NVIDIA boards keep NVML's figures.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from mabat._shared import platform as plat
from mabat._shared.models import ProblemKind, Problems
from mabat.sections.gpu.models import GpuMemory, GpuTelemetry

SOURCE = "perfcounters"

# Fixed script; never built from user input. Aggregates per (luid, engine type) in
# PowerShell so the payload is a dozen numbers rather than hundreds of instances.
_QUERY = (
    "$ErrorActionPreference = 'Stop'; "
    "$s = Get-Counter -Counter '\\GPU Engine(*)\\Utilization Percentage',"
    "'\\GPU Adapter Memory(*)\\Dedicated Usage','\\GPU Adapter Memory(*)\\Shared Usage'; "
    "$eng = @{}; $mem = @{}; "
    "foreach ($x in $s.CounterSamples) { "
    "$n = $x.InstanceName; $p = $x.Path; "
    "if ($n -match 'luid_(0x[0-9a-f]+_0x[0-9a-f]+)') { $l = $matches[1] } else { continue }; "
    "if ($p -like '*GPU Engine*') { "
    "if ($n -match 'engtype_([a-z0-9_]+)$') { $k = $l + '|' + $matches[1]; "
    "$eng[$k] = [double]$eng[$k] + $x.CookedValue } } "
    "elseif ($p -like '*Dedicated Usage*') { $k = $l + '|dedicated'; "
    "$mem[$k] = [double]$mem[$k] + $x.CookedValue } "
    "elseif ($p -like '*Shared Usage*') { $k = $l + '|shared'; "
    "$mem[$k] = [double]$mem[$k] + $x.CookedValue } "
    "}; "
    "$adapters = @(Get-ChildItem 'HKLM:\\SOFTWARE\\Microsoft\\DirectX' "
    "-ErrorAction SilentlyContinue | ForEach-Object { $q = Get-ItemProperty $_.PSPath; "
    "if ($q.Description -and $q.AdapterLuid) { @{ description = [string]$q.Description; "
    "luid = ('0x{0:x8}_0x{1:x8}' -f [int64]($q.AdapterLuid -shr 32), "
    "[int64]($q.AdapterLuid -band 0xFFFFFFFF)); "
    "dedicated_total = [int64]$q.DedicatedVideoMemory } } }); "
    "@{ engines = $eng; memory = $mem; adapters = $adapters } | ConvertTo-Json -Depth 4 -Compress"
)

_KEY = re.compile(r"^(?P<luid>0x[0-9a-f]+_0x[0-9a-f]+)\|(?P<kind>[a-z0-9_]+)$", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class CounterReading:
    """One adapter's live figures, keyed by the name the DirectX registry gives it."""

    luid: str
    name: str
    telemetry: GpuTelemetry


def _split_keys(table: Any) -> dict[str, dict[str, float]]:
    """``{"luid|kind": value}`` -> ``{luid: {kind: value}}`` (luids lower-cased)."""
    out: dict[str, dict[str, float]] = {}
    if not isinstance(table, dict):
        return out
    for key, value in table.items():
        match = _KEY.match(str(key))
        if not match or not isinstance(value, int | float):
            continue
        luid = match.group("luid").lower()
        out.setdefault(luid, {})[match.group("kind").lower()] = float(value)
    return out


def _adapters(rows: Any) -> dict[str, tuple[str, int | None]]:
    """luid -> (description, dedicated total bytes) from the registry rows."""
    found: dict[str, tuple[str, int | None]] = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or not row.get("luid") or not row.get("description"):
            continue
        total = row.get("dedicated_total")
        found[str(row["luid"]).lower()] = (
            str(row["description"]),
            int(total) if isinstance(total, int | float) and total > 0 else None,
        )
    return found


def parse(payload: Any) -> tuple[CounterReading, ...]:
    """Turn the script's JSON into one reading per adapter that has engine counters."""
    if not isinstance(payload, dict):
        return ()
    engines = _split_keys(payload.get("engines"))
    memory = _split_keys(payload.get("memory"))
    adapters = _adapters(payload.get("adapters"))
    readings = []
    for luid, per_engine in engines.items():
        name, total = adapters.get(luid, (None, None))
        if name is None:
            continue  # counters for an adapter the registry does not describe
        busiest = max(per_engine.values(), default=0.0)
        used = memory.get(luid, {}).get("dedicated")
        shared = memory.get(luid, {}).get("shared")
        vram = None
        if used is not None and total:
            vram = GpuMemory(
                total_bytes=total,
                used_bytes=int(used),
                free_bytes=max(total - int(used), 0),
                percent=round(100.0 * used / total, 1),
            )
        readings.append(
            CounterReading(
                luid=luid,
                name=name,
                telemetry=GpuTelemetry(
                    memory=vram,
                    utilization_percent=round(min(busiest, 100.0), 1),
                    memory_controller_percent=None,
                    encoder_percent=per_engine.get("videoencode"),
                    decoder_percent=per_engine.get("videodecode"),
                    temperature_c=None,
                    temperature_slowdown_c=None,
                    power_watts=None,
                    power_limit_watts=None,
                    fan_percent=None,
                    clocks=None,
                    performance_state=None,
                    pcie_generation=None,
                    pcie_width=None,
                    processes=None,
                    engine_percent={k: round(v, 1) for k, v in sorted(per_engine.items())},
                    shared_memory_used_bytes=int(shared) if shared is not None else None,
                ),
            )
        )
    return tuple(readings)


def read_counters(problems: Problems) -> tuple[CounterReading, ...] | None:
    """Live readings for every adapter the counters and registry agree on (Windows)."""
    if not plat.IS_WINDOWS:
        problems.add(
            SOURCE, ProblemKind.UNSUPPORTED_PLATFORM, "GPU performance counters are Windows-only"
        )
        return None
    try:
        result = plat.run_powershell(_QUERY, timeout=30.0)
        payload = json.loads(result.stdout or "null")
    except (plat.CommandError, NotImplementedError, json.JSONDecodeError) as exc:
        problems.add(SOURCE, ProblemKind.BACKEND_ERROR, f"{type(exc).__name__}: {exc}")
        return None
    readings = parse(payload)
    if not readings:
        problems.add(SOURCE, ProblemKind.NOT_PRESENT, "no GPU engine counters reported")
    return readings
