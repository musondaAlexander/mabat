"""Typer application: commands map 1:1 onto library calls and render or emit JSON."""

from __future__ import annotations

from typing import Annotated

import typer

import mabat
from mabat._shared.serialize import to_json
from mabat.cli.render import console, error_console, render_health, render_section

app = typer.Typer(
    help="Observe your machine: CPU, GPU, memory, storage, network and OS.",
    no_args_is_help=True,
    add_completion=False,
)

JsonFlag = Annotated[bool, typer.Option("--json", help="Emit JSON instead of a table.")]


@app.command()
def version() -> None:
    """Print the installed mabat version."""
    console.print(mabat.__version__)


@app.command()
def health(json_: JsonFlag = False) -> None:
    """Show which data sources work on this machine. Exit status 1 if a core one is missing."""
    report = mabat.health()
    if json_:
        console.print_json(to_json(report))
    else:
        render_health(report)
    if not report.ok:
        raise typer.Exit(code=1)


def _complete_section(incomplete: str) -> list[str]:
    return [name for name in mabat.section_names() if name.startswith(incomplete)]


SectionArg = Annotated[
    str,
    typer.Argument(
        help="Which section to read: " + ", ".join(mabat.section_names()) + ".",
        autocompletion=_complete_section,
    ),
]


@app.command()
def show(section: SectionArg, json_: JsonFlag = False) -> None:
    """Read one section (e.g. `mabat show cpu`). Exit status 1 if nothing could be read."""
    collectors = mabat.collectors()
    collect = collectors.get(section)
    if collect is None:
        error_console.print(
            f"[red]unknown section {section!r}[/red] - choose from: {', '.join(collectors)}"
        )
        raise typer.Exit(code=2)
    result = collect()
    if json_:
        console.print_json(to_json(result))
    else:
        render_section(result)
    if not result.available:
        raise typer.Exit(code=1)
