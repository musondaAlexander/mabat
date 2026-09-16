"""CPU models: static identity (what chip is this) and a live usage sample."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CpuCache:
    """Cache sizes in bytes; ``None`` when the platform does not expose a level."""

    l1_data_bytes: int | None
    l1_instruction_bytes: int | None
    l2_bytes: int | None
    l3_bytes: int | None


@dataclass(frozen=True, slots=True)
class CpuIdentity:
    brand: str | None
    vendor: str | None
    architecture: str | None
    bits: int | None
    physical_cores: int | None
    logical_cores: int | None
    advertised_hz: int | None
    family: int | None
    model: int | None
    stepping: int | None
    cache: CpuCache
    flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CpuFrequency:
    """MHz. ``min``/``max`` are ``None`` when the platform reports them as unknown."""

    current_mhz: float | None
    min_mhz: float | None
    max_mhz: float | None


@dataclass(frozen=True, slots=True)
class CpuTimes:
    """Cumulative seconds since boot. ``other`` holds platform-specific buckets
    (``interrupt``/``dpc`` on Windows, ``iowait``/``irq``/``steal``... on Linux)."""

    user_seconds: float
    system_seconds: float
    idle_seconds: float
    other_seconds: dict[str, float]


@dataclass(frozen=True, slots=True)
class CpuStats:
    context_switches: int
    interrupts: int
    soft_interrupts: int
    syscalls: int


@dataclass(frozen=True, slots=True)
class CpuUsage:
    """Utilisation sampled over ``sample_seconds`` plus instantaneous counters."""

    percent: float
    per_core_percent: tuple[float, ...]
    sample_seconds: float
    frequency: CpuFrequency | None
    times: CpuTimes | None
    stats: CpuStats | None
    load_average: tuple[float, float, float] | None


@dataclass(frozen=True, slots=True)
class CpuReport:
    identity: CpuIdentity | None
    usage: CpuUsage | None
