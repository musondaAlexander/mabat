"""Renderer for the health report."""

from __future__ import annotations

from rich.console import RenderableType
from rich.table import Table
from rich.text import Text

from mabat._health import Health, ProviderStatus
from mabat.cli.render.common import assemble

OK = "[green]yes[/green]"
NO = "[red]no[/red]"
OPTIONAL_NO = "[yellow]no[/yellow]"


def _availability(provider: ProviderStatus) -> str:
    if provider.available:
        return OK
    return NO if provider.required else OPTIONAL_NO


def render_health(report: Health) -> RenderableType:
    table = Table(title=f"mabat {report.mabat_version} health", title_justify="left")
    table.add_column("provider", style="bold")
    table.add_column("available", justify="center")
    table.add_column("required", justify="center")
    table.add_column("powers")
    table.add_column("detail", style="dim")

    for provider in report.providers:
        table.add_row(
            provider.name,
            _availability(provider),
            "yes" if provider.required else "",
            provider.powers,
            Text(provider.detail),
        )

    status = (
        Text("core providers available", style="green")
        if report.ok
        else Text("core providers missing", style="red")
    )
    summary = Text.assemble(
        f"{report.platform_release} | Python {report.python} | ",
        "elevated" if report.is_admin else "not elevated",
        " | ",
        status,
    )
    return assemble(table, summary)
