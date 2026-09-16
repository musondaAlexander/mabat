"""Latency benchmark: time every section cold and warm against a budget.

Budgets are generous on purpose: they catch regressions (a collector that suddenly
spawns a process per call), not slow hardware. Per-process scans on hosts with security
software hooking handle access can legitimately take seconds.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from rich.console import RenderableType
from rich.table import Table
from rich.text import Text

import mabat
from mabat.cli.render.common import assemble

# warm-call budget in seconds; cold calls pay one-off costs (py-cpuinfo, WMI) and are
# reported but not judged
BUDGETS: dict[str, float] = {
    "cpu": 1.5,
    "memory": 0.2,
    "system": 10.0,
    "storage": 3.0,
    "gpu": 1.5,
    "sensors": 3.0,
    "network": 1.0,
    "snapshot": 20.0,
}
DEFAULT_BUDGET = 5.0


@dataclass(frozen=True, slots=True)
class Timing:
    section: str
    cold_seconds: float
    warm_seconds: float
    budget_seconds: float
    ok: bool


@dataclass(frozen=True, slots=True)
class BenchReport:
    timings: tuple[Timing, ...]
    ok: bool


def _time(call: Callable[[], object]) -> float:
    started = time.perf_counter()
    call()
    return time.perf_counter() - started


def run_bench(only: list[str] | None = None) -> BenchReport:
    targets: dict[str, Callable[[], object]] = dict(mabat.collectors())
    targets["snapshot"] = mabat.snapshot
    if only:
        targets = {name: call for name, call in targets.items() if name in only}
    timings = []
    for name, collect in targets.items():
        cold = _time(collect)
        warm = _time(collect)
        budget = BUDGETS.get(name, DEFAULT_BUDGET)
        timings.append(Timing(name, round(cold, 3), round(warm, 3), budget, warm <= budget))
    return BenchReport(tuple(timings), all(t.ok for t in timings))


def render_bench(report: BenchReport) -> RenderableType:
    table = Table(show_edge=False, pad_edge=False, box=None, header_style="bold")
    table.add_column("section", style="bold cyan")
    table.add_column("cold", justify="right")
    table.add_column("warm", justify="right")
    table.add_column("budget", justify="right", style="dim")
    table.add_column("status")
    for t in report.timings:
        table.add_row(
            t.section,
            f"{t.cold_seconds:.2f} s",
            f"{t.warm_seconds:.2f} s",
            f"{t.budget_seconds:.1f} s",
            Text("ok", style="green") if t.ok else Text("over budget", style="bold red"),
        )
    note = Text(
        "cold = first call in a process (one-off caches); warm = judged against the budget",
        style="dim",
    )
    return assemble(table, note)
