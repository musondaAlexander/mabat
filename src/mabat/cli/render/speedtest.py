"""Renderer for the speedtest section."""

from __future__ import annotations

from rich.console import RenderableType
from rich.text import Text

from mabat._shared.models import Section
from mabat.cli.render.common import DOT, assemble, heading, kv_table, problems_footer
from mabat.sections.speedtest import SpeedtestReport


def fmt_bps(value: float) -> str:
    """Bits per second -> '93.4 Mbit/s' (decimal units, as speedtest.net reports)."""
    for unit in ("bit/s", "kbit/s", "Mbit/s", "Gbit/s"):
        if value < 1000 or unit == "Gbit/s":
            return f"{value:.1f} {unit}"
        value /= 1000
    return f"{value:.1f} Gbit/s"


def render_speedtest(section: Section[SpeedtestReport]) -> RenderableType:
    report = section.data
    if report is None:
        return assemble(Text("Speedtest: unavailable", style="bold red"), problems_footer(section))
    table = kv_table()
    table.add_row("download", Text(fmt_bps(report.download_bps), style="bold green"))
    table.add_row("upload", Text(fmt_bps(report.upload_bps), style="bold green"))
    table.add_row("ping", f"{report.ping_ms:.1f} ms")
    if report.server:
        server = report.server
        where = DOT.join(p for p in (server.sponsor, server.name, server.country) if p)
        distance = f"{DOT}{server.distance_km:.0f} km" if server.distance_km is not None else ""
        table.add_row("server", Text(f"{where}{distance}"))
    if report.isp or report.public_ip:
        table.add_row("client", Text(DOT.join(p for p in (report.isp, report.public_ip) if p)))
    table.add_row("took", f"{report.duration_seconds:g} s")
    return assemble(heading("Speedtest"), table, problems_footer(section))
