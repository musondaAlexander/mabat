"""GPU models: one ``GpuDevice`` per adapter, with live ``GpuTelemetry`` where a vendor
library (NVML) provides it and static identity only where it does not (WMI)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GpuMemory:
    total_bytes: int
    used_bytes: int
    free_bytes: int
    percent: float


@dataclass(frozen=True, slots=True)
class GpuClocks:
    """MHz; ``graphics_max_mhz`` is the board's rated maximum."""

    graphics_mhz: int | None
    memory_mhz: int | None
    graphics_max_mhz: int | None


@dataclass(frozen=True, slots=True)
class GpuTelemetry:
    """Live readings. ``None`` means the vendor library does not expose that value for
    this board (laptops rarely report fan speed, for example)."""

    memory: GpuMemory | None
    utilization_percent: float | None
    memory_controller_percent: float | None
    encoder_percent: float | None
    decoder_percent: float | None
    temperature_c: int | None
    temperature_slowdown_c: int | None
    power_watts: float | None
    power_limit_watts: float | None
    fan_percent: int | None
    clocks: GpuClocks | None
    performance_state: int | None
    pcie_generation: int | None
    pcie_width: int | None
    processes: int | None


@dataclass(frozen=True, slots=True)
class GpuDisplay:
    width: int
    height: int
    refresh_hz: int | None


@dataclass(frozen=True, slots=True)
class GpuDevice:
    """``physical`` is False for software adapters (virtual displays, remote-desktop
    drivers). ``memory_total_bytes`` from WMI is capped at 4 GiB by the WMI schema; the
    NVML figure is exact and wins when both are present."""

    name: str
    vendor: str | None
    sources: tuple[str, ...]
    physical: bool
    driver_version: str | None
    memory_total_bytes: int | None
    bus_id: str | None
    uuid: str | None
    vbios: str | None
    processor: str | None
    display: GpuDisplay | None
    telemetry: GpuTelemetry | None


@dataclass(frozen=True, slots=True)
class GpuReport:
    devices: tuple[GpuDevice, ...]
    nvml_driver_version: str | None
