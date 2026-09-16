"""Typer application: commands map 1:1 onto library calls and render or emit JSON."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from datetime import datetime
from typing import Annotated, Any

import typer
from rich.console import Group, RenderableType
from rich.live import Live
from rich.text import Text

import mabat
from mabat._shared.serialize import to_json
from mabat.cli.render import console, error_console, render_health, render_section
from mabat.cli.render.snapshot import render_snapshot

SNAPSHOT = "snapshot"

app = typer.Typer(
    help="Observe your machine: CPU, GPU, memory, storage, network and OS.",
    no_args_is_help=True,
    add_completion=False,
)

JsonFlag = Annotated[bool, typer.Option("--json", help="Emit JSON instead of a table.")]
OnlyOpt = Annotated[
    list[str] | None,
    typer.Option("--only", help="Collect only these sections (repeat or comma-separate)."),
]
SkipOpt = Annotated[
    list[str] | None,
    typer.Option("--skip", help="Leave these sections out (repeat or comma-separate)."),
]
ConnectionsFlag = Annotated[
    bool, typer.Option("--connections", help="Include the socket table in the network section.")
]


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


# --- targets: a section name or "snapshot" ------------------------------------------------


def _targets() -> tuple[str, ...]:
    return (*mabat.section_names(), SNAPSHOT)


def _complete_target(incomplete: str) -> list[str]:
    return [name for name in _targets() if name.startswith(incomplete)]


TargetArg = Annotated[
    str,
    typer.Argument(
        help="A section (" + ", ".join(mabat.section_names()) + ") or 'snapshot' for all.",
        autocompletion=_complete_target,
    ),
]


def _split(values: list[str] | None) -> list[str] | None:
    if values is None:
        return None
    return [part.strip() for value in values for part in value.split(",") if part.strip()]


class Target:
    """What to collect and how to draw it; the same object serves show, watch and snapshot."""

    def __init__(
        self,
        name: str,
        *,
        only: list[str] | None = None,
        skip: list[str] | None = None,
        connections: bool = False,
    ) -> None:
        self.name = name
        if name == SNAPSHOT:
            options = {"connections": True} if connections else {}
            self._collect: Callable[[], Any] = lambda: mabat.snapshot(only, skip, **options)
            self._render: Callable[[Any], RenderableType] = render_snapshot
        else:
            collectors = mabat.collectors()
            collect = collectors.get(name)
            if collect is None:
                error_console.print(
                    f"[red]unknown section {name!r}[/red] - choose from: {', '.join(_targets())}"
                )
                raise typer.Exit(code=2)
            self._collect = collect
            self._render = render_section

    def collect(self) -> Any:
        try:
            return self._collect()
        except ValueError as exc:  # unknown --only/--skip names
            error_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=2) from None

    def render(self, result: Any) -> RenderableType:
        return self._render(result)

    @staticmethod
    def available(result: Any) -> bool:
        if isinstance(result, mabat.Snapshot):
            return any(s.available for s in mabat.sections_of(result).values())
        return bool(result.available)


def _emit(target: Target, result: Any, json_: bool) -> None:
    if json_:
        console.print_json(to_json(result))
    else:
        console.print(target.render(result))
    if not Target.available(result):
        raise typer.Exit(code=1)


@app.command()
def show(section: TargetArg, json_: JsonFlag = False) -> None:
    """Read one section once (e.g. `mabat show cpu`). Exit status 1 if nothing could be read."""
    target = Target(section)
    _emit(target, target.collect(), json_)


@app.command()
def snapshot(
    json_: JsonFlag = False,
    only: OnlyOpt = None,
    skip: SkipOpt = None,
    connections: ConnectionsFlag = False,
) -> None:
    """Every section at once: a one-screen overview, or one JSON document with --json."""
    target = Target(SNAPSHOT, only=_split(only), skip=_split(skip), connections=connections)
    _emit(target, target.collect(), json_)


IntervalOpt = Annotated[
    float,
    typer.Option("--interval", "-i", min=0.1, help="Seconds between refreshes."),
]
CountOpt = Annotated[
    int,
    typer.Option("--count", "-n", min=0, help="Stop after this many readings (0 = forever)."),
]


def _ticks(collect: Callable[[], Any], interval: float, count: int) -> Iterator[Any]:
    """Yield readings at most every ``interval`` seconds (collection time is absorbed)."""
    taken = 0
    while count == 0 or taken < count:
        started = time.monotonic()
        yield collect()
        taken += 1
        if count and taken >= count:
            break
        time.sleep(max(0.0, interval - (time.monotonic() - started)))


def _frame(target: Target, result: Any, interval: float) -> Group:
    stamp = result.collected_at.astimezone().strftime("%H:%M:%S")
    header = Text.assemble(
        ("mabat watch ", "bold"),
        (target.name, "bold cyan"),
        (f"  every {interval:g} s  {stamp}  ", "dim"),
        ("Ctrl+C to stop", "dim italic"),
    )
    return Group(header, Text(""), target.render(result))


@app.command()
def watch(
    section: TargetArg,
    interval: IntervalOpt = 1.0,
    count: CountOpt = 0,
    json_: JsonFlag = False,
    only: OnlyOpt = None,
    skip: SkipOpt = None,
    connections: ConnectionsFlag = False,
) -> None:
    """Refresh a section - or the whole snapshot - live (e.g. `mabat watch cpu`).

    With --json, prints one JSON document per line (NDJSON) instead - pipe it anywhere.
    --only/--skip/--connections apply when watching 'snapshot'.
    """
    target = Target(section, only=_split(only), skip=_split(skip), connections=connections)
    ticks = _ticks(target.collect, interval, count)
    try:
        if json_:
            for reading in ticks:
                console.file.write(to_json(reading) + "\n")
                console.file.flush()
            return
        with Live(console=console, refresh_per_second=8, transient=False) as live:
            for reading in ticks:
                live.update(_frame(target, reading, interval))
    except KeyboardInterrupt:
        console.print(Text(f"stopped at {datetime.now().strftime('%H:%M:%S')}", style="dim"))


@app.command()
def connections(json_: JsonFlag = False) -> None:
    """List open sockets, netstat style, with owning process names."""
    result = mabat.connections()
    if json_:
        console.print_json(to_json(result))
    else:
        console.print(render_section(result))
    if not result.available:
        raise typer.Exit(code=1)


@app.command("cli")
def interactive() -> None:
    """Enter interactive mode: type commands like `show cpu` until `quit`."""
    from mabat.cli.repl import repl

    repl(app)


app.command("shell", hidden=True)(interactive)
