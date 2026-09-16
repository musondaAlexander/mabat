"""GPU section: adapters with live telemetry (NVIDIA via NVML) or identity (WMI)."""

from mabat.sections.gpu.collector import gpu
from mabat.sections.gpu.models import (
    GpuClocks,
    GpuDevice,
    GpuDisplay,
    GpuMemory,
    GpuReport,
    GpuTelemetry,
)

__all__ = [
    "GpuClocks",
    "GpuDevice",
    "GpuDisplay",
    "GpuMemory",
    "GpuReport",
    "GpuTelemetry",
    "gpu",
]
