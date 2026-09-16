"""Renderer for the memory section."""

from __future__ import annotations

from rich.text import Text

from mabat._shared.models import Section
from mabat.cli.render.common import (
    DOT,
    bar,
    console,
    fmt_bytes,
    kv_table,
    pct_text,
    render_problems,
)
from mabat.sections.memory import MemoryReport


def render_memory(section: Section[MemoryReport]) -> None:
    report = section.data
    if report is None:
        console.print(Text("Memory: unavailable", style="bold red"))
        render_problems(section)
        return

    if report.virtual:
        vm = report.virtual
        console.print(Text.assemble(("RAM  ", "bold"), bar(vm.percent), "  ", pct_text(vm.percent)))
        table = kv_table()
        table.add_row("total", fmt_bytes(vm.total_bytes))
        table.add_row("used", fmt_bytes(vm.used_bytes))
        table.add_row("available", fmt_bytes(vm.available_bytes))
        table.add_row("free", fmt_bytes(vm.free_bytes))
        for name, value in vm.other_bytes.items():
            table.add_row(name, fmt_bytes(value))
        console.print(table)

    if report.swap:
        sw = report.swap
        console.print()
        console.print(Text.assemble(("Swap ", "bold"), bar(sw.percent), "  ", pct_text(sw.percent)))
        table = kv_table()
        table.add_row("total", fmt_bytes(sw.total_bytes))
        table.add_row("used", fmt_bytes(sw.used_bytes))
        table.add_row("free", fmt_bytes(sw.free_bytes))
        table.add_row(
            "paged since boot",
            f"in {fmt_bytes(sw.swapped_in_bytes)}{DOT}out {fmt_bytes(sw.swapped_out_bytes)}",
        )
        console.print(table)

    render_problems(section)
