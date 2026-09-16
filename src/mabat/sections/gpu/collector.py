"""Compose NVML telemetry and WMI identity into one list of adapters."""

from __future__ import annotations

import dataclasses

from mabat._shared.models import ProblemKind, Problems, Section, attempt, run_collector
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


def gpu() -> Section[GpuReport]:
    """Every graphics adapter: live telemetry for NVIDIA boards, identity for the rest."""

    def collect(problems: Problems) -> GpuReport | None:
        nvml_result = attempt(problems, "nvml", lambda: read_nvml(problems))
        nvml_devices, driver = nvml_result if nvml_result else ((), None)
        wmi_devices = attempt(problems, "wmi", lambda: read_wmi(problems)) or ()
        devices = merge(nvml_devices, wmi_devices)
        if not devices:
            if nvml_result is not None and not nvml_devices:
                problems.add("nvml", ProblemKind.NOT_PRESENT, "no NVIDIA GPU detected")
            return None
        return GpuReport(devices=devices, nvml_driver_version=driver)

    return run_collector(SECTION, collect)
