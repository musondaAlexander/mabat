"""Renderer for the CPU section."""

from __future__ import annotations

from rich.table import Table
from rich.text import Text

from mabat._shared.models import Section
from mabat.cli.render.common import (
    DOT,
    ELLIPSIS,
    bar,
    console,
    fmt_bytes,
    fmt_hz,
    fmt_int,
    fmt_seconds,
    kv_table,
    pct_text,
    render_problems,
)
from mabat.sections.cpu import CpuIdentity, CpuReport, CpuUsage

_FLAGS_SHOWN = 8


def _identity(identity: CpuIdentity) -> None:
    console.print(Text(identity.brand or "Unknown CPU", style="bold"))
    table = kv_table()
    cores = "-"
    if identity.physical_cores or identity.logical_cores:
        cores = f"{identity.physical_cores or '?'} cores / {identity.logical_cores or '?'} threads"
    bits = f" ({identity.bits}-bit)" if identity.bits else ""
    table.add_row("vendor", identity.vendor or "-")
    table.add_row("architecture", f"{identity.architecture or '-'}{bits}")
    table.add_row("cores", cores)
    table.add_row("advertised", fmt_hz(identity.advertised_hz))
    cache = identity.cache
    table.add_row(
        "cache",
        f"L1d {fmt_bytes(cache.l1_data_bytes, precision=0)}  "
        f"L1i {fmt_bytes(cache.l1_instruction_bytes, precision=0)}  "
        f"L2 {fmt_bytes(cache.l2_bytes, precision=0)}  "
        f"L3 {fmt_bytes(cache.l3_bytes, precision=0)}",
    )
    table.add_row(
        "family/model/step",
        f"{identity.family or '-'} / {identity.model or '-'} / {identity.stepping or '-'}",
    )
    if identity.flags:
        shown = ", ".join(identity.flags[:_FLAGS_SHOWN])
        hidden = len(identity.flags) - _FLAGS_SHOWN
        more = f" {ELLIPSIS} +{hidden} more" if hidden > 0 else ""
        table.add_row("flags", f"{len(identity.flags)}: {shown}{more}")
    console.print(table)


def _usage(usage: CpuUsage) -> None:
    window = f"{usage.sample_seconds:g} s sample" if usage.sample_seconds else "since last call"
    console.print(
        Text.assemble(("Usage ", "bold"), (f"({window})  ", "dim"), pct_text(usage.percent))
    )

    cores = Table.grid(padding=(0, 1))
    cores.add_column(style="dim", no_wrap=True)
    cores.add_column(no_wrap=True)
    cores.add_column(justify="right", no_wrap=True)
    for index, percent in enumerate(usage.per_core_percent):
        cores.add_row(f"core {index:>2}", bar(percent), pct_text(percent))
    console.print(cores)

    table = kv_table()
    if usage.frequency:
        freq = usage.frequency
        table.add_row(
            "frequency",
            f"{fmt_hz(freq.current_mhz, mhz=True)} now{DOT}"
            f"min {fmt_hz(freq.min_mhz, mhz=True)}{DOT}max {fmt_hz(freq.max_mhz, mhz=True)}",
        )
    if usage.times:
        times = usage.times
        buckets = [
            f"user {fmt_seconds(times.user_seconds)}",
            f"system {fmt_seconds(times.system_seconds)}",
            f"idle {fmt_seconds(times.idle_seconds)}",
        ]
        buckets += [f"{name} {fmt_seconds(value)}" for name, value in times.other_seconds.items()]
        table.add_row("time since boot", DOT.join(buckets))
    if usage.stats:
        stats = usage.stats
        table.add_row(
            "counters",
            DOT.join(
                [
                    f"ctx switches {fmt_int(stats.context_switches)}",
                    f"interrupts {fmt_int(stats.interrupts)}",
                    f"soft {fmt_int(stats.soft_interrupts)}",
                    f"syscalls {fmt_int(stats.syscalls)}",
                ]
            ),
        )
    if usage.load_average:
        one, five, fifteen = usage.load_average
        table.add_row("load average", f"{one:.2f}  {five:.2f}  {fifteen:.2f}  (1 / 5 / 15 min)")
    console.print(table)


def render_cpu(section: Section[CpuReport]) -> None:
    report = section.data
    if report is None:
        console.print(Text("CPU: unavailable", style="bold red"))
    else:
        if report.identity:
            _identity(report.identity)
        if report.usage:
            console.print()
            _usage(report.usage)
    render_problems(section)
