"""Renderer for the system section."""

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
    fmt_seconds,
    heading,
    kv_table,
    pct_text,
    problems_footer,
)
from mabat.sections.system import Battery, OsIdentity, ProcessSummary, SystemReport, Uptime, User


def _os(os_identity: OsIdentity, uptime: Uptime | None) -> RenderableType:
    table = kv_table()
    table.add_row("system", f"{os_identity.system} {os_identity.release} ({os_identity.version})")
    if os_identity.distribution:
        table.add_row("distribution", Text(os_identity.distribution))
    table.add_row("platform", Text(os_identity.platform))
    table.add_row("machine", os_identity.machine)
    table.add_row("python", os_identity.python)
    if uptime:
        booted = uptime.boot_time.astimezone().strftime("%Y-%m-%d %H:%M:%S")
        table.add_row("uptime", f"{fmt_seconds(uptime.uptime_seconds)}{DOT}booted {booted}")
    return assemble(heading(os_identity.hostname), table)


def _users(users: tuple[User, ...]) -> RenderableType:
    if not users:
        return Text("no logged-in users", style="dim")
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold cyan", no_wrap=True)
    table.add_column()
    for user in users:
        since = user.started.astimezone().strftime("%Y-%m-%d %H:%M") if user.started else "-"
        where = f" from {user.host}" if user.host else ""
        terminal = f" on {user.terminal}" if user.terminal else ""
        table.add_row(Text(user.name), Text(f"since {since}{where}{terminal}"))
    return assemble(heading("Users"), table)


def _battery(battery: Battery) -> RenderableType:
    if battery.power_plugged is True:
        state = "plugged in"
    elif battery.power_plugged is False:
        state = "on battery"
    else:
        state = "power state unknown"
    left = f"{DOT}{fmt_seconds(battery.seconds_left)} left" if battery.seconds_left else ""
    # thresholds apply to what is *used*; for a battery that is the drained share
    drained_style = pct_text(100.0 - battery.percent).style
    return Text.assemble(
        ("Battery ", "bold"),
        Text(bar(battery.percent).plain, style=drained_style),
        "  ",
        Text(f"{battery.percent:.0f} %", style=drained_style),
        (f"{DOT}{state}{left}", "dim"),
    )


def _processes(summary: ProcessSummary) -> RenderableType:
    window = f"{summary.sample_seconds:g} s sample" if summary.sample_seconds else "since last call"
    title = Text.assemble(
        ("Processes ", "bold"),
        (f"{summary.total} total{DOT}top {summary.top_n} by CPU ({window})", "dim"),
    )
    table = Table(show_edge=False, pad_edge=False, box=None, header_style="bold")
    table.add_column("pid", justify="right", style="dim")
    table.add_column("name")
    table.add_column("cpu", justify="right")
    table.add_column("memory", justify="right")
    table.add_column("rss", justify="right")
    table.add_column("thr", justify="right", style="dim")
    table.add_column("user", style="dim")
    for proc in summary.top:
        table.add_row(
            str(proc.pid),
            Text(proc.name),
            pct_text(proc.cpu_percent),
            pct_text(proc.memory_percent),
            fmt_bytes(proc.memory_rss_bytes),
            "-" if proc.threads is None else str(proc.threads),
            Text(proc.username or "-"),
        )
    return assemble(title, table)


def render_system(section: Section[SystemReport]) -> RenderableType:
    report = section.data
    if report is None:
        return assemble(Text("System: unavailable", style="bold red"), problems_footer(section))
    blank = Text("")
    return assemble(
        _os(report.os, report.uptime) if report.os else None,
        blank if report.users is not None else None,
        _users(report.users) if report.users is not None else None,
        blank if report.battery else None,
        _battery(report.battery) if report.battery else None,
        blank if report.processes else None,
        _processes(report.processes) if report.processes else None,
        problems_footer(section),
    )
