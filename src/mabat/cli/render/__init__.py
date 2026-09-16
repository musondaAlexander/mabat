"""Rich renderers: one per model, dispatched by section name. Renderers *build* a
renderable and never print; the app decides whether it goes to the console, a live view
or nowhere. No data collection here."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from rich.console import RenderableType
from rich.json import JSON

from mabat._shared.models import Section
from mabat._shared.serialize import to_json
from mabat.cli.render.common import console, error_console, problems_footer
from mabat.cli.render.cpu import render_cpu
from mabat.cli.render.health import render_health
from mabat.cli.render.memory import render_memory

RENDERERS: dict[str, Callable[[Section[Any]], RenderableType]] = {
    "cpu": render_cpu,
    "memory": render_memory,
}


def render_section(section: Section[Any]) -> RenderableType:
    """A section's dedicated view, or pretty JSON when none exists yet."""
    renderer = RENDERERS.get(section.name)
    if renderer is None:
        return JSON(to_json(section))
    return renderer(section)


__all__ = [
    "RENDERERS",
    "console",
    "error_console",
    "problems_footer",
    "render_cpu",
    "render_health",
    "render_memory",
    "render_section",
]
