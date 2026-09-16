"""Rich renderers for mabat models. One function per model; no data collection here."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from mabat._health import Health, ProviderStatus

console = Console()
error_console = Console(stderr=True)

OK = "[green]yes[/green]"
NO = "[red]no[/red]"
OPTIONAL_NO = "[yellow]no[/yellow]"


def _availability(provider: ProviderStatus) -> str:
    if provider.available:
        return OK
    return NO if provider.required else OPTIONAL_NO


def render_health(report: Health) -> None:
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
            provider.detail,
        )

    console.print(table)
    status = (
        "[green]core providers available[/green]"
        if report.ok
        else "[red]core providers missing[/red]"
    )
    console.print(
        f"{report.platform_release} | Python {report.python} | "
        f"{'elevated' if report.is_admin else 'not elevated'} | {status}"
    )
