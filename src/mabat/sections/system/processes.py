"""Per-process sampling, tuned for hosts where every per-process handle is expensive.

Two tiers: a cheap pass over *every* process (CPU delta + resident memory, inside
``oneshot``) ranks them; the expensive attributes (username, status, threads, start
time) are fetched for the top-N only. With ``sample_seconds=0`` the priming pass is
skipped and the CPU delta spans the time since the previous call - psutil's
``process_iter`` keeps the counters alive between calls - which is what a watch loop wants.
"""

from __future__ import annotations

from collections.abc import Callable, Collection
from datetime import UTC, datetime
from typing import Any

from mabat._shared.models import ProblemKind, Problems
from mabat.sections.system.models import ProcessInfo

# Never "cmdline", "environ" or "cwd": privacy guard P2.


def _exceptions(psutil: Any) -> tuple[type[BaseException], type[BaseException]]:
    """(gone, denied) exception types; fall back to builtins for a stand-in psutil."""
    gone = getattr(psutil, "NoSuchProcess", ProcessLookupError)
    denied = getattr(psutil, "AccessDenied", PermissionError)
    return gone, denied


def _prime(procs: list[Any], gone: type[BaseException], denied: type[BaseException]) -> None:
    """Start every process's CPU counter so the next reading is a real delta."""
    for proc in procs:
        try:
            proc.cpu_percent(None)
        except (gone, denied):
            continue


def _cheap(proc: Any, logical_cores: int, total_memory: int) -> ProcessInfo:
    with proc.oneshot():
        cpu = float(proc.cpu_percent(None)) / logical_cores
        rss = int(proc.memory_info().rss)
        name = str(proc.name() or "?")
    return ProcessInfo(
        pid=int(proc.pid),
        name=name,
        username=None,
        status="",
        cpu_percent=round(cpu, 2),
        memory_percent=round(100.0 * rss / total_memory, 2) if total_memory else 0.0,
        memory_rss_bytes=rss,
        threads=None,
        created=None,
    )


def _enrich(info: ProcessInfo, proc: Any, denied: type[BaseException]) -> ProcessInfo:
    """Add the expensive attributes; a denied one simply stays unknown."""

    def read(attr: str) -> Any:
        try:
            return getattr(proc, attr)()
        except denied:
            return None

    created = read("create_time")
    return ProcessInfo(
        pid=info.pid,
        name=info.name,
        username=read("username") or None,
        status=str(read("status") or "unknown"),
        cpu_percent=info.cpu_percent,
        memory_percent=info.memory_percent,
        memory_rss_bytes=info.memory_rss_bytes,
        threads=read("num_threads"),
        created=datetime.fromtimestamp(created, tz=UTC) if created else None,
    )


def read_processes(
    psutil: Any,
    problems: Problems,
    sample_seconds: float,
    top_n: int,
    sleep: Callable[[float], None],
    hidden_names: Collection[str] = (),
) -> tuple[list[ProcessInfo], int, int]:
    """Returns (top-N processes, total visible, inaccessible count).

    ``hidden_names`` are excluded from the ranking but still counted in the total.
    """
    gone, denied = _exceptions(psutil)
    logical_cores = int(psutil.cpu_count(logical=True) or 1)
    total_memory = int(psutil.virtual_memory().total)
    procs = list(psutil.process_iter())

    if sample_seconds:
        _prime(procs, gone, denied)
        sleep(sample_seconds)

    sampled: list[tuple[ProcessInfo, Any]] = []
    inaccessible = 0
    for proc in procs:
        try:
            sampled.append((_cheap(proc, logical_cores, total_memory), proc))
        except gone:
            continue
        except denied:
            inaccessible += 1

    total = len(sampled)
    ranked = [item for item in sampled if item[0].name not in hidden_names]
    ranked.sort(key=lambda item: (item[0].cpu_percent, item[0].memory_rss_bytes), reverse=True)
    top: list[ProcessInfo] = []
    for info, proc in ranked[:top_n]:
        try:
            top.append(_enrich(info, proc, denied))
        except gone:
            continue

    if inaccessible:
        problems.add(
            "psutil.process_iter",
            ProblemKind.PERMISSION_DENIED,
            f"{inaccessible} processes could not be inspected; run elevated to see them",
        )
    return top, total, inaccessible
