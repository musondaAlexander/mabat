"""Compose NVML telemetry and WMI identity into one list of adapters."""

from __future__ import annotations

import dataclasses

from mabat._shared.config import settings
from mabat._shared.models import ProblemKind, Problems, Section, attempt, run_collector
from mabat.sections.gpu.counters import CounterReading, read_counters
from mabat.sections.gpu.models import GpuDevice, GpuReport
from mabat.sections.gpu.nvml import read_nvml
from mabat.sections.gpu.wmi import read_wmi

SECTION = "gpu"


def _same_adapter(nvml_device: GpuDevice, wmi_device: GpuDevice) -> bool:
    return nvml_device.name.strip().lower() == wmi_device.name.strip().lower()


def merge(
    nvml_devices: tuple[GpuDevice, ...], wmi_devices: tuple[GpuDevice, ...]
) -> tuple[GpuDevice, ...]:
    """NVML devices first (exact memory, live telemetry), enriched with the matching WMI
    row's display info; remaining WMI rows follow as identity-only adapters."""
    merged: list[GpuDevice] = []
    leftovers = list(wmi_devices)
    for device in nvml_devices:
        match = next((w for w in leftovers if _same_adapter(device, w)), None)
        if match is None:
            merged.append(device)
            continue
        leftovers.remove(match)
        merged.append(
            dataclasses.replace(
                device,
                sources=(*device.sources, *match.sources),
                processor=device.processor or match.processor,
                display=match.display,
            )
        )
    merged.extend(sorted(leftovers, key=lambda d: (not d.physical, d.name)))
    return tuple(merged)


def apply_counters(
    devices: tuple[GpuDevice, ...], readings: tuple[CounterReading, ...]
) -> tuple[GpuDevice, ...]:
    """Give adapters without vendor telemetry the performance-counter figures, matched by
    name; adapters that already have telemetry (NVML) keep it."""
    by_name = {r.name.strip().lower(): r for r in readings}
    updated = []
    for device in devices:
        reading = by_name.get(device.name.strip().lower())
        if device.telemetry is None and reading is not None:
            device = dataclasses.replace(
                device,
                sources=(*device.sources, "perfcounters"),
                telemetry=reading.telemetry,
                memory_total_bytes=(
                    reading.telemetry.memory.total_bytes
                    if reading.telemetry.memory
                    else device.memory_total_bytes
                ),
            )
        updated.append(device)
    return tuple(updated)


def gpu(*, counters: bool | None = None) -> Section[GpuReport]:
    """Every graphics adapter: live telemetry for NVIDIA boards, identity for the rest.

    ``counters=True`` (or ``[gpu] counters`` in settings) also reads Windows GPU
    performance counters so non-NVIDIA adapters get load and memory figures; ~3-5 s.
    """
    use_counters = settings().gpu_counters if counters is None else bool(counters)

    def collect(problems: Problems) -> GpuReport | None:
        nvml_result = attempt(problems, "nvml", lambda: read_nvml(problems))
        nvml_devices, driver = nvml_result if nvml_result else ((), None)
        wmi_devices = attempt(problems, "wmi", lambda: read_wmi(problems)) or ()
        devices = merge(nvml_devices, wmi_devices)
        if not devices:
            if nvml_result is not None and not nvml_devices:
                problems.add("nvml", ProblemKind.NOT_PRESENT, "no NVIDIA GPU detected")
            return None
        if use_counters:
            readings = attempt(problems, "perfcounters", lambda: read_counters(problems))
            if readings:
                devices = apply_counters(devices, readings)
        return GpuReport(devices=devices, nvml_driver_version=driver)

    return run_collector(SECTION, collect)
