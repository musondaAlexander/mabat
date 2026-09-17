"""Partitions, usage and disk I/O via psutil; SMART via the ``smart`` provider."""

from __future__ import annotations

from typing import Any

from mabat._shared import platform as plat
from mabat._shared.models import ProblemKind, Problems, Section, attempt, run_collector
from mabat.sections.storage.models import DiskIo, Partition, StorageReport
from mabat.sections.storage.smart import read_smart

SECTION = "storage"


def _partition(psutil: Any, part: Any, problems: Problems) -> Partition:
    usage = attempt(
        problems,
        f"psutil.disk_usage({part.mountpoint})",
        lambda: psutil.disk_usage(part.mountpoint),
    )
    return Partition(
        device=str(part.device),
        mountpoint=str(part.mountpoint),
        fstype=str(part.fstype),
        options=str(part.opts),
        total_bytes=int(usage.total) if usage else None,
        used_bytes=int(usage.used) if usage else None,
        free_bytes=int(usage.free) if usage else None,
        percent=float(usage.percent) if usage else None,
    )


def read_partitions(
    psutil: Any, problems: Problems, *, all_partitions: bool = False
) -> tuple[Partition, ...] | None:
    parts = attempt(
        problems, "psutil.disk_partitions", lambda: psutil.disk_partitions(all=all_partitions)
    )
    if parts is None:
        return None
    return tuple(_partition(psutil, part, problems) for part in parts)


# psutil documents read_time/write_time as milliseconds, and they are on Linux and macOS.
# On Windows the values are whole seconds: DISK_PERFORMANCE counts 100-ns ticks and
# psutil divides by 10^7 (verified against Win32_PerfRawData_PerfDisk_PhysicalDisk).
_TIME_UNIT_SECONDS = 1.0 if plat.IS_WINDOWS else 1.0 / 1000.0


def _seconds(value: float | None) -> float | None:
    return None if value is None else float(value) * _TIME_UNIT_SECONDS


def read_io(psutil: Any, problems: Problems) -> tuple[DiskIo, ...] | None:
    counters = attempt(
        problems, "psutil.disk_io_counters", lambda: psutil.disk_io_counters(perdisk=True)
    )
    if counters is None:
        return None
    if not counters:
        problems.add("psutil.disk_io_counters", ProblemKind.NOT_PRESENT, "no disk I/O counters")
        return ()
    disks = []
    for name, io in counters.items():
        read_seconds = _seconds(io.read_time)
        write_seconds = _seconds(io.write_time)
        disks.append(
            DiskIo(
                name=str(name),
                read_count=int(io.read_count),
                write_count=int(io.write_count),
                read_bytes=int(io.read_bytes),
                write_bytes=int(io.write_bytes),
                read_seconds=read_seconds if read_seconds is not None else 0.0,
                write_seconds=write_seconds if write_seconds is not None else 0.0,
                busy_seconds=_seconds(getattr(io, "busy_time", None)),
            )
        )
    return tuple(disks)


def storage(*, all_partitions: bool = False, smart: bool = True) -> Section[StorageReport]:
    """Partitions with usage, per-disk I/O counters and (when available) SMART health.

    ``all_partitions`` includes pseudo/virtual filesystems; ``smart=False`` skips the
    smartctl round-trip, which can take a second or two.
    """

    def collect(problems: Problems) -> StorageReport | None:
        psutil = plat.optional_import("psutil")
        partitions = io = None
        if psutil is None:
            problems.add("psutil", ProblemKind.MISSING_DEPENDENCY, "psutil is not installed")
        else:
            partitions = read_partitions(psutil, problems, all_partitions=all_partitions)
            io = read_io(psutil, problems)
        devices = attempt(problems, "smart", lambda: read_smart(problems)) if smart else None
        if partitions is None and io is None and devices is None:
            return None
        return StorageReport(partitions=partitions, io=io, smart=devices)

    return run_collector(SECTION, collect)
