"""Renderer for the storage section."""

from __future__ import annotations

from rich.console import RenderableType
from rich.table import Table
from rich.text import Text

from mabat._shared.models import Section
from mabat.cli.render.common import (
    DOT,
    assemble,
    bar,
    fmt_bytes,
    fmt_int,
    fmt_seconds,
    heading,
    pct_text,
    problems_footer,
)
from mabat.sections.storage import DiskIo, Partition, SmartDevice, StorageReport

_ATTRIBUTES_SHOWN = 6


def _partitions(partitions: tuple[Partition, ...]) -> RenderableType:
    table = Table(show_edge=False, pad_edge=False, box=None, header_style="bold")
    table.add_column("mount")
    table.add_column("fs", style="dim")
    table.add_column("used")
    table.add_column("", justify="right")
    table.add_column("size", justify="right")
    table.add_column("free", justify="right")
    for part in partitions:
        table.add_row(
            Text(part.mountpoint),
            Text(part.fstype or "-"),
            bar(part.percent, width=16),
            pct_text(part.percent),
            fmt_bytes(part.total_bytes),
            fmt_bytes(part.free_bytes),
        )
    return assemble(heading("Partitions"), table)


def _io(disks: tuple[DiskIo, ...]) -> RenderableType:
    if not disks:
        return Text("no disk I/O counters", style="dim")
    table = Table(show_edge=False, pad_edge=False, box=None, header_style="bold")
    table.add_column("disk", no_wrap=True)
    table.add_column("read", justify="right")
    table.add_column("written", justify="right")
    table.add_column("reads", justify="right", style="dim")
    table.add_column("writes", justify="right", style="dim")
    table.add_column("busy r / w", justify="right", style="dim")
    for disk in disks:
        table.add_row(
            Text(disk.name),
            fmt_bytes(disk.read_bytes),
            fmt_bytes(disk.write_bytes),
            fmt_int(disk.read_count),
            fmt_int(disk.write_count),
            f"{fmt_seconds(disk.read_seconds)} / {fmt_seconds(disk.write_seconds)}",
        )
    return assemble(heading("Disk I/O since boot"), table)


def _assessment(verdict: str | None) -> Text:
    if verdict is None:
        return Text("unknown", style="dim")
    styles = {"PASS": "green", "WARN": "yellow", "FAIL": "bold red"}
    return Text(verdict, style=styles.get(verdict.upper(), ""))


def _smart(devices: tuple[SmartDevice, ...]) -> RenderableType:
    if not devices:
        return Text("no SMART-capable devices reported", style="dim")
    parts: list[RenderableType] = [heading("SMART health")]
    for dev in devices:
        temp = f"{DOT}{dev.temperature_c} C" if dev.temperature_c is not None else ""
        parts.append(
            Text.assemble(
                (dev.name, "bold cyan"),
                "  ",
                _assessment(dev.assessment),
                (
                    f"{DOT}{dev.model or '-'}{DOT}{fmt_bytes(dev.capacity_bytes)}"
                    f"{DOT}{dev.interface or '-'}{temp}",
                    "dim",
                ),
            )
        )
        if dev.attributes:
            table = Table.grid(padding=(0, 2))
            table.add_column(style="dim", justify="right")
            table.add_column()
            table.add_column(justify="right")
            table.add_column(style="dim")
            for attr in dev.attributes[:_ATTRIBUTES_SHOWN]:
                table.add_row(
                    str(attr.id) if attr.id is not None else "-",
                    Text(attr.name),
                    str(attr.value) if attr.value is not None else "-",
                    Text(f"raw {attr.raw}") if attr.raw else Text(""),
                )
            hidden = len(dev.attributes) - _ATTRIBUTES_SHOWN
            if hidden > 0:
                table.add_row(
                    "", Text(f"+{hidden} more attributes (use --json)", style="dim"), "", ""
                )
            parts.append(table)
    return assemble(*parts)


def render_storage(section: Section[StorageReport]) -> RenderableType:
    report = section.data
    if report is None:
        return assemble(Text("Storage: unavailable", style="bold red"), problems_footer(section))
    blank = Text("")
    return assemble(
        _partitions(report.partitions) if report.partitions is not None else None,
        blank if report.io is not None else None,
        _io(report.io) if report.io is not None else None,
        blank if report.smart is not None else None,
        _smart(report.smart) if report.smart is not None else None,
        problems_footer(section),
    )
