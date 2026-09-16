"""Renderers for the network section and the standalone connections table."""

from __future__ import annotations

from rich.console import RenderableType
from rich.table import Table
from rich.text import Text

from mabat._shared.models import Section
from mabat.cli.render.common import (
    DOT,
    assemble,
    fmt_bytes,
    fmt_int,
    heading,
    kv_table,
    problems_footer,
)
from mabat.sections.network import ConnectionsReport, Interface, NetworkReport, Rates

_CONNECTIONS_SHOWN = 40


def fmt_rate(value: float | None) -> str:
    """Bytes per second -> '1.2 MiB/s' (or '-' before a second sample exists)."""
    return "-" if value is None else f"{fmt_bytes(int(value))}/s"


def _rates(rates: Rates | None) -> str:
    if rates is None:
        return "-"
    return f"{fmt_rate(rates.sent_bytes_per_s)} up{DOT}{fmt_rate(rates.recv_bytes_per_s)} down"


def _interface_row(table: Table, iface: Interface) -> None:
    ipv4 = [a.address for a in iface.addresses if a.family == "ipv4"]
    if iface.is_up is None:
        state = Text("?", style="dim")
    elif iface.is_up:
        state = Text("up", style="green")
    else:
        state = Text("down", style="dim")
    counters = iface.counters
    rates = iface.rates
    table.add_row(
        Text(iface.name),
        state,
        Text(", ".join(ipv4) or "-"),
        Text(f"{iface.speed_mbps}" if iface.speed_mbps else "-", style="dim"),
        fmt_bytes(counters.bytes_sent) if counters else "-",
        fmt_bytes(counters.bytes_recv) if counters else "-",
        Text(fmt_rate(rates.sent_bytes_per_s) if rates else "-"),
        Text(fmt_rate(rates.recv_bytes_per_s) if rates else "-"),
    )


def _interfaces(interfaces: tuple[Interface, ...]) -> RenderableType:
    shown = [i for i in interfaces if not i.hidden]
    hidden = [i for i in interfaces if i.hidden]
    table = Table(show_edge=False, pad_edge=False, box=None, header_style="bold")
    table.add_column("interface", overflow="fold", ratio=3)
    table.add_column("state", no_wrap=True)
    table.add_column("ipv4", no_wrap=True, min_width=15)
    table.add_column("Mb/s", justify="right", no_wrap=True)
    table.add_column("sent", justify="right", no_wrap=True)
    table.add_column("recv", justify="right", no_wrap=True)
    table.add_column("up/s", justify="right", no_wrap=True)
    table.add_column("down/s", justify="right", no_wrap=True)
    for iface in sorted(shown, key=lambda i: (not i.is_up, i.name)):
        _interface_row(table, iface)
    note = None
    if hidden:
        names = ", ".join(i.name for i in hidden)
        note = Text(f"{len(hidden)} hidden: {names} (present in --json)", style="dim")
    return assemble(heading("Interfaces  (MAC addresses and MTU in --json)"), table, note)


def _connections(report: ConnectionsReport) -> RenderableType:
    title = Text.assemble(
        ("Connections ", "bold"),
        (
            f"{len(report.connections)} sockets{DOT}{report.established} established"
            f"{DOT}{report.listening} listening",
            "dim",
        ),
    )
    table = Table(show_edge=False, pad_edge=False, box=None, header_style="bold")
    table.add_column("proto", no_wrap=True)
    table.add_column("local", overflow="fold", min_width=15)
    table.add_column("remote", overflow="fold", min_width=15)
    table.add_column("status", no_wrap=True)
    table.add_column("pid", justify="right", style="dim", no_wrap=True)
    table.add_column("process", overflow="fold", min_width=12)
    for conn in report.connections[:_CONNECTIONS_SHOWN]:
        remote = f"{conn.remote_address}:{conn.remote_port}" if conn.remote_address else "-"
        status_style = (
            "green" if conn.status == "ESTABLISHED" else "dim" if conn.status == "NONE" else ""
        )
        table.add_row(
            f"{conn.protocol}{'6' if conn.family == 'ipv6' else ''}",
            Text(f"{conn.local_address}:{conn.local_port}"),
            Text(remote),
            Text(conn.status, style=status_style),
            str(conn.pid) if conn.pid else "-",
            Text(conn.process or "-"),
        )
    more = len(report.connections) - _CONNECTIONS_SHOWN
    note = Text(f"+{more} more (use --json)", style="dim") if more > 0 else None
    return assemble(title, table, note)


def render_network(section: Section[NetworkReport]) -> RenderableType:
    report = section.data
    if report is None:
        return assemble(Text("Network: unavailable", style="bold red"), problems_footer(section))
    summary = kv_table()
    summary.add_row("hostname", Text(report.hostname))
    summary.add_row("outbound ip", Text(report.outbound_ip or "-"))
    if report.totals:
        totals = report.totals
        packets = fmt_int(totals.packets_sent + totals.packets_recv)
        summary.add_row(
            "total traffic",
            f"{fmt_bytes(totals.bytes_sent)} sent{DOT}{fmt_bytes(totals.bytes_recv)} received"
            f"{DOT}{packets} packets",
        )
        summary.add_row("throughput", _rates(report.total_rates))
        errors = report.totals.errors_in + report.totals.errors_out
        drops = report.totals.drops_in + report.totals.drops_out
        if errors or drops:
            summary.add_row("errors / drops", Text(f"{errors} / {drops}", style="yellow"))
    return assemble(
        summary,
        Text(""),
        _interfaces(report.interfaces) if report.interfaces else None,
        Text("") if report.connections else None,
        _connections(report.connections) if report.connections else None,
        problems_footer(section),
    )


def render_connections(section: Section[ConnectionsReport]) -> RenderableType:
    report = section.data
    if report is None:
        return assemble(
            Text("Connections: unavailable", style="bold red"), problems_footer(section)
        )
    return assemble(_connections(report), problems_footer(section))
