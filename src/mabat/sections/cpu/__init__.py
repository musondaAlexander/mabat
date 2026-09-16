"""CPU section: chip identity and live utilisation."""

from mabat.sections.cpu.collector import cpu
from mabat.sections.cpu.models import (
    CpuCache,
    CpuFrequency,
    CpuIdentity,
    CpuReport,
    CpuStats,
    CpuTimes,
    CpuUsage,
)

__all__ = [
    "CpuCache",
    "CpuFrequency",
    "CpuIdentity",
    "CpuReport",
    "CpuStats",
    "CpuTimes",
    "CpuUsage",
    "cpu",
]
