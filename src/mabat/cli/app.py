"""Typer application: commands map 1:1 onto library calls and render or emit JSON."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from datetime import datetime
from typing import Annotated, Any

import typer
from rich.console import Group
from rich.live import Live
from rich.text import Text

import mabat
from mabat._shared.models import Section
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
        console.print(render_health(report))
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


def _collector(section: str) -> Callable[[], Section[Any]]:
    collectors = mabat.collectors()
    collect = collectors.get(section)
    if collect is None:
        error_console.print(
            f"[red]unknown section {section!r}[/red] - choose from: {', '.join(collectors)}"
        )
        raise typer.Exit(code=2)
    return collect


@app.command()
def show(section: SectionArg, json_: JsonFlag = False) -> None:
    """Read one section once (e.g. `mabat show cpu`). Exit status 1 if nothing could be read."""
    result = _collector(section)()
    if json_:
        console.print_json(to_json(result))
    else:
        console.print(render_section(result))
    if not result.available:
        raise typer.Exit(code=1)


IntervalOpt = Annotated[
    float,
    typer.Option("--interval", "-i", min=0.1, help="Seconds between refreshes."),
]
CountOpt = Annotated[
    int,
    typer.Option("--count", "-n", min=0, help="Stop after this many readings (0 = forever)."),
]


def _ticks(
    collect: Callable[[], Section[Any]], interval: float, count: int
) -> Iterator[Section[Any]]:
    """Yield readings at most every ``interval`` seconds (collection time is absorbed)."""
    taken = 0
    while count == 0 or taken < count:
        started = time.monotonic()
        yield collect()
        taken += 1
        if count and taken >= count:
            break
        time.sleep(max(0.0, interval - (time.monotonic() - started)))


def _frame(section: Section[Any], interval: float) -> Group:
    stamp = section.collected_at.astimezone().strftime("%H:%M:%S")
    header = Text.assemble(
        ("mabat watch ", "bold"),
        (section.name, "bold cyan"),
        (f"  every {interval:g} s  {stamp}  ", "dim"),
        ("Ctrl+C to stop", "dim italic"),
    )
    return Group(header, Text(""), render_section(section))


@app.command()
def watch(
    section: SectionArg, interval: IntervalOpt = 1.0, count: CountOpt = 0, json_: JsonFlag = False
) -> None:
    """Refresh one section live in the terminal (e.g. `mabat watch cpu`).

    With --json, prints one JSON document per line (NDJSON) instead - pipe it anywhere.
    """
    collect = _collector(section)
    ticks = _ticks(collect, interval, count)
    try:
        if json_:
            for reading in ticks:
                console.file.write(to_json(reading) + "\n")
                console.file.flush()
            return
        with Live(console=console, refresh_per_second=8, transient=False) as live:
            for reading in ticks:
                live.update(_frame(reading, interval))
    except KeyboardInterrupt:
        console.print(Text(f"stopped at {datetime.now().strftime('%H:%M:%S')}", style="dim"))


@app.command("cli")
def interactive() -> None:
    """Enter interactive mode: type commands like `show cpu` until `quit`."""
    from mabat.cli.repl import repl

    repl(app)


app.command("shell", hidden=True)(interactive)
