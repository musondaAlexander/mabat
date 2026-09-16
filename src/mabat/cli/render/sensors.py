"""Renderer for the sensors section."""

from __future__ import annotations

from rich.console import RenderableType
from rich.table import Table
from rich.text import Text

from mabat._shared.models import Section
from mabat.cli.render.common import assemble, heading, problems_footer, temp_text
from mabat.sections.sensors import Fan, Power, SensorsReport, Temperature


def _temperatures(temperatures: tuple[Temperature, ...]) -> RenderableType:
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold cyan", no_wrap=True)
    table.add_column()
    table.add_column(justify="right")
    table.add_column(style="dim")
    for temp in temperatures:
        limits = []
        if temp.high_c is not None:
            limits.append(f"high {temp.high_c:.0f}")
        if temp.critical_c is not None:
            limits.append(f"critical {temp.critical_c:.0f}")
        table.add_row(
            Text(temp.hardware),
            Text(temp.label),
            temp_text(temp.celsius, temp.critical_c),
            Text(", ".join(limits)),
        )
    return assemble(heading("Temperatures"), table)


def _fans(fans: tuple[Fan, ...]) -> RenderableType:
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold cyan", no_wrap=True)
    table.add_column()
    table.add_column(justify="right")
    for fan in fans:
        table.add_row(Text(fan.hardware), Text(fan.label), f"{fan.rpm:.0f} rpm")
    return assemble(heading("Fans"), table)


def _powers(powers: tuple[Power, ...]) -> RenderableType:
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold cyan", no_wrap=True)
    table.add_column()
    table.add_column(justify="right")
    for power in powers:
        table.add_row(Text(power.hardware), Text(power.label), f"{power.watts:.1f} W")
    return assemble(heading("Power"), table)


def render_sensors(section: Section[SensorsReport]) -> RenderableType:
    report = section.data
    if report is None:
        return assemble(Text("Sensors: unavailable", style="bold red"), problems_footer(section))
    blank = Text("")
    return assemble(
        Text(f"via {report.provider}", style="dim"),
        _temperatures(report.temperatures) if report.temperatures else None,
        blank if report.temperatures and report.fans else None,
        _fans(report.fans) if report.fans else None,
        blank if (report.temperatures or report.fans) and report.powers else None,
        _powers(report.powers) if report.powers else None,
        problems_footer(section),
    )
