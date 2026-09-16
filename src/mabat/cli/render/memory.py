"""Renderer for the memory section."""

from __future__ import annotations

from rich.console import RenderableType
from rich.text import Text

from mabat._shared.models import Section
from mabat.cli.render.common import (
    DOT,
    assemble,
    bar,
    fmt_bytes,
    kv_table,
    pct_text,
    problems_footer,
)
from mabat.sections.memory import MemoryReport, SwapMemory, VirtualMemory


def _virtual(vm: VirtualMemory) -> RenderableType:
    title = Text.assemble(("RAM  ", "bold"), bar(vm.percent), "  ", pct_text(vm.percent))
    table = kv_table()
    table.add_row("total", fmt_bytes(vm.total_bytes))
    table.add_row("used", fmt_bytes(vm.used_bytes))
    table.add_row("available", fmt_bytes(vm.available_bytes))
    table.add_row("free", fmt_bytes(vm.free_bytes))
    for name, value in vm.other_bytes.items():
        table.add_row(name, fmt_bytes(value))
    return assemble(title, table)


def _swap(sw: SwapMemory) -> RenderableType:
    title = Text.assemble(("Swap ", "bold"), bar(sw.percent), "  ", pct_text(sw.percent))
    table = kv_table()
    table.add_row("total", fmt_bytes(sw.total_bytes))
    table.add_row("used", fmt_bytes(sw.used_bytes))
    table.add_row("free", fmt_bytes(sw.free_bytes))
    table.add_row(
        "paged since boot",
        f"in {fmt_bytes(sw.swapped_in_bytes)}{DOT}out {fmt_bytes(sw.swapped_out_bytes)}",
    )
    return assemble(title, table)


def render_memory(section: Section[MemoryReport]) -> RenderableType:
    report = section.data
    if report is None:
        return assemble(Text("Memory: unavailable", style="bold red"), problems_footer(section))
    return assemble(
        _virtual(report.virtual) if report.virtual else None,
        Text("") if report.virtual and report.swap else None,
        _swap(report.swap) if report.swap else None,
        problems_footer(section),
    )
