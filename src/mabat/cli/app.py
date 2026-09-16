"""Typer application: commands map 1:1 onto library calls and render or emit JSON."""

from __future__ import annotations

from typing import Annotated

import typer

import mabat
from mabat._shared.serialize import to_json
from mabat.cli.render import console, render_health

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
