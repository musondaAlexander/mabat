"""System RAM and swap via psutil."""

from __future__ import annotations

from typing import Any

from mabat._shared import platform as plat
from mabat._shared.models import ProblemKind, Problems, Section, attempt, run_collector
from mabat.sections.memory.models import MemoryReport, SwapMemory, VirtualMemory

SECTION = "memory"
_VIRTUAL_CORE = ("total", "available", "used", "free", "percent")


def read_virtual(psutil: Any, problems: Problems) -> VirtualMemory | None:
    vm = attempt(problems, "psutil.virtual_memory", psutil.virtual_memory)
    if vm is None:
        return None
    fields = vm._asdict()
    return VirtualMemory(
        total_bytes=int(fields["total"]),
        available_bytes=int(fields["available"]),
        used_bytes=int(fields["used"]),
        free_bytes=int(fields["free"]),
        percent=float(fields["percent"]),
        other_bytes={
            name: int(value) for name, value in fields.items() if name not in _VIRTUAL_CORE
        },
    )


def read_swap(psutil: Any, problems: Problems) -> SwapMemory | None:
    sm = attempt(problems, "psutil.swap_memory", psutil.swap_memory)
    if sm is None:
        return None
    return SwapMemory(
        total_bytes=int(sm.total),
        used_bytes=int(sm.used),
        free_bytes=int(sm.free),
        percent=float(sm.percent),
        swapped_in_bytes=int(sm.sin),
        swapped_out_bytes=int(sm.sout),
    )


def memory() -> Section[MemoryReport]:
    """System RAM and swap. Cheap (no sampling); safe to poll every second."""

    def collect(problems: Problems) -> MemoryReport | None:
        psutil = plat.optional_import("psutil")
        if psutil is None:
            problems.add("psutil", ProblemKind.MISSING_DEPENDENCY, "psutil is not installed")
            return None
        virtual = read_virtual(psutil, problems)
        swap = read_swap(psutil, problems)
        if virtual is None and swap is None:
            return None
        return MemoryReport(virtual=virtual, swap=swap)

    return run_collector(SECTION, collect)
