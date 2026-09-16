"""Renderer for the effective settings and their sources."""

from __future__ import annotations

from rich.console import RenderableType
from rich.table import Table
from rich.text import Text

from mabat._shared.config import ResolvedSettings
from mabat._shared.serialize import flatten
from mabat.cli.render.common import assemble, heading, kv_table


def render_settings(resolved: ResolvedSettings) -> RenderableType:
    sources = Table.grid(padding=(0, 2))
    sources.add_column(style="bold cyan", no_wrap=True)
    sources.add_column(no_wrap=True)
    sources.add_column(overflow="fold")
    for source in resolved.sources:
        state = Text("applied", style="green") if source.applied else Text("not found", style="dim")
        sources.add_row(source.kind, state, Text(source.path))

    values = kv_table()
    for key, value in flatten(resolved.settings).items():
        values.add_row(key, Text(str(value)))
    return assemble(
        heading("Sources (later overrides earlier)"),
        sources,
        Text(""),
        heading("Effective settings"),
        values,
    )
