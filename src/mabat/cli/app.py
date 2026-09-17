"""Typer application: commands map 1:1 onto library calls and render or emit JSON."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Group
from rich.live import Live
from rich.text import Text

import mabat
from mabat._shared.serialize import to_dict, to_json
from mabat.cli.bench import render_bench, run_bench
from mabat.cli.history import read_history, render_history
from mabat.cli.render import console, error_console, render_health, render_section
from mabat.cli.render.common import DOT
from mabat.cli.render.settings import render_settings
from mabat.cli.stats import SessionStats, headline
from mabat.cli.targets import SNAPSHOT, Target, collector_options, targets

app = typer.Typer(
    help="Observe your machine: CPU, GPU, memory, storage, network and OS.",
    no_args_is_help=True,
    add_completion=True,
)

# --- shared flags ------------------------------------------------------------------------

JsonFlag = Annotated[bool, typer.Option("--json", help="Emit JSON instead of a table.")]
RedactFlag = Annotated[
    bool,
    typer.Option("--redact", help="Mask hostnames, users, addresses and serials before output."),
]
OnlyOpt = Annotated[
    list[str] | None,
    typer.Option("--only", help="Collect only these sections (repeat or comma-separate)."),
]
SkipOpt = Annotated[
    list[str] | None,
    typer.Option("--skip", help="Leave these sections out (repeat or comma-separate)."),
]
SampleOpt = Annotated[
    float | None,
    typer.Option("--sample", min=0.0, help="Sample window in seconds for cpu/system (0 = delta)."),
]
TopOpt = Annotated[
    int | None,
    typer.Option("--top", min=0, help="Processes to rank in system (0 = count only, fast)."),
]
AllPartitionsFlag = Annotated[
    bool, typer.Option("--all-partitions", help="storage: include pseudo/virtual filesystems.")
]
NoSmartFlag = Annotated[
    bool, typer.Option("--no-smart", help="storage: skip the smartctl round-trip.")
]
ConnectionsFlag = Annotated[
    bool, typer.Option("--connections", help="network: include the socket table.")
]
AllFlag = Annotated[bool, typer.Option("--all", help="network: show hidden interfaces too.")]
CountersFlag = Annotated[
    bool,
    typer.Option(
        "--counters",
        help="gpu: read Windows performance counters for non-NVIDIA adapters (~5 s).",
    ),
]
LogOpt = Annotated[
    Path | None,
    typer.Option("--log", help="Append every reading to this file as NDJSON, one per line."),
]


def _split(values: list[str] | None) -> list[str] | None:
    if values is None:
        return None
    return [part.strip() for value in values for part in value.split(",") if part.strip()]


@app.callback()
def _global(
    no_color: Annotated[bool, typer.Option("--no-color", help="Plain output, no styling.")] = False,
    width: Annotated[
        int | None, typer.Option("--width", min=40, help="Render width in columns.")
    ] = None,
) -> None:
    """Observe your machine: CPU, GPU, memory, storage, network and OS."""
    for target in (console, error_console):
        if no_color:
            target.no_color = True
        if width is not None:
            target.width = width


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


@app.command()
def config(json_: JsonFlag = False) -> None:
    """Print the effective settings and where they came from."""
    resolved = mabat.resolve_settings()
    if json_:
        console.print_json(to_json(resolved))
    else:
        console.print(render_settings(resolved))


# --- show / snapshot / watch ------------------------------------------------------------------


def _complete_target(incomplete: str) -> list[str]:
    return [name for name in targets() if name.startswith(incomplete)]


TargetArg = Annotated[
    str,
    typer.Argument(
        help="A section (" + ", ".join(mabat.section_names()) + ") or 'snapshot' for all.",
        autocompletion=_complete_target,
    ),
]


def _emit(target: Target, result: Any, json_: bool, redact: bool = False) -> None:
    if redact:
        result = mabat.redact(result)
    if json_:
        console.print_json(to_json(result))
    else:
        console.print(target.render(result))
    if not Target.available(result):
        raise typer.Exit(code=1)


@app.command()
def show(
    section: TargetArg,
    json_: JsonFlag = False,
    redact: RedactFlag = False,
    sample: SampleOpt = None,
    top: TopOpt = None,
    all_partitions: AllPartitionsFlag = False,
    no_smart: NoSmartFlag = False,
    connections: ConnectionsFlag = False,
    counters: CountersFlag = False,
    all_: AllFlag = False,
) -> None:
    """Read one section once (e.g. `mabat show cpu`). Exit status 1 if nothing could be read."""
    options = collector_options(
        sample=sample,
        top=top,
        all_partitions=all_partitions,
        no_smart=no_smart,
        connections=connections,
        counters=counters,
    )
    target = Target(section, options=options, show_hidden=all_)
    _emit(target, target.collect(), json_, redact)


@app.command()
def snapshot(
    json_: JsonFlag = False,
    redact: RedactFlag = False,
    only: OnlyOpt = None,
    skip: SkipOpt = None,
    sample: SampleOpt = None,
    top: TopOpt = None,
    all_partitions: AllPartitionsFlag = False,
    no_smart: NoSmartFlag = False,
    connections: ConnectionsFlag = False,
    counters: CountersFlag = False,
) -> None:
    """Every section at once: a one-screen overview, or one JSON document with --json."""
    options = collector_options(
        sample=sample,
        top=top,
        all_partitions=all_partitions,
        no_smart=no_smart,
        connections=connections,
        counters=counters,
    )
    target = Target(SNAPSHOT, options=options, only=_split(only), skip=_split(skip))
    _emit(target, target.collect(), json_, redact)


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


def _frame(target: Target, result: Any, interval: float, stats: SessionStats) -> Group:
    stamp = result.collected_at.astimezone().strftime("%H:%M:%S")
    header = Text.assemble(
        ("mabat watch ", "bold"),
        (target.name, "bold cyan"),
        (f"  every {interval:g} s  {stamp}  ", "dim"),
        ("Ctrl+C to stop", "dim italic"),
    )
    summary = stats.summary(DOT)
    session = Text(f"session {summary}", style="dim") if summary else None
    parts = [header, session, Text(""), target.render(result)]
    return Group(*(part for part in parts if part is not None))


@app.command()
def watch(
    section: TargetArg,
    interval: IntervalOpt = 1.0,
    count: CountOpt = 0,
    json_: JsonFlag = False,
    redact: RedactFlag = False,
    log: LogOpt = None,
    only: OnlyOpt = None,
    skip: SkipOpt = None,
    sample: SampleOpt = None,
    top: TopOpt = None,
    all_partitions: AllPartitionsFlag = False,
    no_smart: NoSmartFlag = False,
    connections: ConnectionsFlag = False,
    counters: CountersFlag = False,
    all_: AllFlag = False,
) -> None:
    """Refresh a section - or the whole snapshot - live (e.g. `mabat watch cpu`).

    With --json, prints one JSON document per line (NDJSON) instead - pipe it anywhere.
    --log appends those same lines to a file while the table stays on screen; replay it
    with `mabat history FILE`. --only/--skip apply when watching 'snapshot'.
    """
    options = collector_options(
        sample=sample,
        top=top,
        all_partitions=all_partitions,
        no_smart=no_smart,
        connections=connections,
        counters=counters,
    )
    target = Target(
        section, options=options, only=_split(only), skip=_split(skip), show_hidden=all_
    )
    ticks = _ticks(target.collect, interval, count)
    sink = log.open("a", encoding="utf-8") if log is not None else None
    stats = SessionStats()
    live = Live(console=console, refresh_per_second=8, transient=False)
    try:
        if not json_:
            live.start()
        for reading in ticks:
            if redact:
                reading = mabat.redact(reading)
            line = to_json(reading)
            if sink is not None:
                sink.write(line + "\n")
                sink.flush()
            if json_:
                console.file.write(line + "\n")
                console.file.flush()
                continue
            payload = to_dict(reading)
            stats.add(headline(payload) if isinstance(payload, dict) else None)
            live.update(_frame(target, reading, interval, stats))
    except KeyboardInterrupt:
        if live.is_started:
            live.stop()
        console.print(Text(f"stopped at {datetime.now().strftime('%H:%M:%S')}", style="dim"))
    finally:
        if live.is_started:
            live.stop()
        if sink is not None:
            sink.close()


@app.command()
def history(
    file: Annotated[
        Path, typer.Argument(help="NDJSON written by `watch --log` or `watch --json`.")
    ],
    json_: JsonFlag = False,
) -> None:
    """Replay a log: one line per reading with its headline number, plus min/avg/max."""
    try:
        frames = read_history(file)
    except (OSError, ValueError) as exc:
        error_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from None
    if json_:
        console.print_json(to_json(frames))
    else:
        console.print(render_history(frames))


@app.command()
def bench(json_: JsonFlag = False, only: OnlyOpt = None) -> None:
    """Time every section cold and warm against a latency budget. Exit 1 if one is over."""
    report = run_bench(_split(only))
    if json_:
        console.print_json(to_json(report))
    else:
        console.print(render_bench(report))
    if not report.ok:
        raise typer.Exit(code=1)


SOCKET_KINDS = (
    "inet",
    "inet4",
    "inet6",
    "tcp",
    "tcp4",
    "tcp6",
    "udp",
    "udp4",
    "udp6",
    "unix",
    "all",
)
KindOpt = Annotated[
    str,
    typer.Option("--kind", help="Socket filter: " + ", ".join(SOCKET_KINDS) + "."),
]


@app.command()
def connections(
    json_: JsonFlag = False, redact: RedactFlag = False, kind: KindOpt = "inet"
) -> None:
    """List open sockets, netstat style, with owning process names."""
    if kind not in SOCKET_KINDS:
        error_console.print(
            f"[red]unknown --kind {kind!r}[/red] - choose from: " + ", ".join(SOCKET_KINDS)
        )
        raise typer.Exit(code=2)
    result = mabat.connections(kind=kind)
    if redact:
        result = mabat.redact(result)
    if json_:
        console.print_json(to_json(result))
    else:
        console.print(render_section(result))
    if not result.available:
        raise typer.Exit(code=1)


@app.command()
def speedtest(json_: JsonFlag = False, redact: RedactFlag = False) -> None:
    """Measure download/upload bandwidth and ping against speedtest.net (~30 s, real traffic)."""
    result = mabat.speedtest()
    if redact:
        result = mabat.redact(result)
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
