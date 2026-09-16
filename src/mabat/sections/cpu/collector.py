"""Live CPU sample via psutil, composed with the cached identity into a ``CpuReport``."""

from __future__ import annotations

from typing import Any

from mabat._shared import platform as plat
from mabat._shared.config import settings
from mabat._shared.models import ProblemKind, Problems, Section, attempt, run_collector
from mabat.sections.cpu.identity import read_identity
from mabat.sections.cpu.models import CpuFrequency, CpuReport, CpuStats, CpuTimes, CpuUsage

SECTION = "cpu"
_CORE_TIME_FIELDS = ("user", "system", "idle")


def _frequency(psutil: Any, problems: Problems) -> CpuFrequency | None:
    freq = attempt(problems, "psutil.cpu_freq", psutil.cpu_freq)
    if freq is None:
        return None
    # psutil reports 0.0 for min/max on platforms that do not expose them
    return CpuFrequency(
        current_mhz=float(freq.current) if freq.current else None,
        min_mhz=float(freq.min) if freq.min else None,
        max_mhz=float(freq.max) if freq.max else None,
    )


def _times(psutil: Any, problems: Problems) -> CpuTimes | None:
    times = attempt(problems, "psutil.cpu_times", psutil.cpu_times)
    if times is None:
        return None
    fields = times._asdict()
    return CpuTimes(
        user_seconds=float(fields.pop("user", 0.0)),
        system_seconds=float(fields.pop("system", 0.0)),
        idle_seconds=float(fields.pop("idle", 0.0)),
        other_seconds={name: float(value) for name, value in fields.items()},
    )


def _stats(psutil: Any, problems: Problems) -> CpuStats | None:
    stats = attempt(problems, "psutil.cpu_stats", psutil.cpu_stats)
    if stats is None:
        return None
    return CpuStats(
        context_switches=int(stats.ctx_switches),
        interrupts=int(stats.interrupts),
        soft_interrupts=int(stats.soft_interrupts),
        syscalls=int(stats.syscalls),
    )


def _load_average(psutil: Any, problems: Problems) -> tuple[float, float, float] | None:
    getloadavg = getattr(psutil, "getloadavg", None)
    if getloadavg is None:
        problems.add("psutil.getloadavg", ProblemKind.UNSUPPORTED_PLATFORM, "no load average")
        return None
    load = attempt(problems, "psutil.getloadavg", getloadavg)
    if load is None:
        return None
    one, five, fifteen = (float(value) for value in load)
    return one, five, fifteen


def read_usage(problems: Problems, sample_seconds: float) -> CpuUsage | None:
    psutil = plat.optional_import("psutil")
    if psutil is None:
        problems.add("psutil", ProblemKind.MISSING_DEPENDENCY, "psutil is not installed")
        return None
    per_core = attempt(
        problems,
        "psutil.cpu_percent",
        lambda: psutil.cpu_percent(interval=sample_seconds or None, percpu=True),
    )
    if not per_core:
        return None
    cores = tuple(float(value) for value in per_core)
    return CpuUsage(
        percent=round(sum(cores) / len(cores), 1),
        per_core_percent=cores,
        sample_seconds=sample_seconds,
        frequency=_frequency(psutil, problems),
        times=_times(psutil, problems),
        stats=_stats(psutil, problems),
        load_average=_load_average(psutil, problems),
    )


def cpu(sample_seconds: float | None = None) -> Section[CpuReport]:
    """Identity plus a utilisation sample taken over ``sample_seconds`` (settings default).

    Pass ``0`` to return the delta since the previous call instead of blocking; the first
    such call reports 0 % per core.
    """
    window = settings().cpu_sample_seconds if sample_seconds is None else float(sample_seconds)
    if window < 0:
        raise ValueError("sample_seconds must not be negative")

    def collect(problems: Problems) -> CpuReport | None:
        identity = attempt(problems, "cpu.identity", lambda: read_identity(problems))
        usage = read_usage(problems, window)
        if identity is None and usage is None:
            return None
        return CpuReport(identity=identity, usage=usage)

    return run_collector(SECTION, collect)
