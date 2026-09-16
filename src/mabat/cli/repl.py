"""Interactive mode: ``mabat cli`` reads commands until ``quit``.

Every line is parsed with shlex and dispatched through the *same* Typer app as the
one-shot CLI, so ``show cpu`` in here and ``mabat show cpu`` outside are one code path.
"""

from __future__ import annotations

import platform as _platform
import shlex

import typer
from rich.table import Table
from rich.text import Text

import mabat
from mabat._shared.platform import PLATFORM_NAME
from mabat.cli.render.common import DOT, UNICODE, console, error_console

PROMPT = "[bold cyan]mabat>[/] "
EXIT_WORDS = frozenset({"quit", "exit", "q"})
HELP_WORDS = frozenset({"help", "?"})
CLEAR_WORDS = frozenset({"clear", "cls"})
NESTED_WORDS = frozenset({"cli", "shell"})
TAGLINE = "observe your machine"

# Block-art wordmark for UTF-8 terminals; figlet-style ASCII for legacy code pages.
LOGO_UNICODE = """\
███╗   ███╗ █████╗ ██████╗  █████╗ ████████╗
████╗ ████║██╔══██╗██╔══██╗██╔══██╗╚══██╔══╝
██╔████╔██║███████║██████╔╝███████║   ██║
██║╚██╔╝██║██╔══██║██╔══██╗██╔══██║   ██║
██║ ╚═╝ ██║██║  ██║██████╔╝██║  ██║   ██║
╚═╝     ╚═╝╚═╝  ╚═╝╚═════╝ ╚═╝  ╚═╝   ╚═╝"""

LOGO_ASCII = r"""
                _           _
 _ __ ___   __ _| |__   __ _| |_
| '_ ` _ \ / _` | '_ \ / _` | __|
| | | | | | (_| | |_) | (_| | |_
|_| |_| |_|\__,_|_.__/ \__,_|\__|""".lstrip("\n")


def logo() -> Text:
    return Text(LOGO_UNICODE if UNICODE else LOGO_ASCII, style="bold cyan")


def _commands(app: typer.Typer) -> list[tuple[str, str]]:
    """(name, one-line help) for every visible command, from the command group itself."""
    group = typer.main.get_command(app)
    commands: dict[str, object] = getattr(group, "commands", {})
    rows = []
    for name in sorted(commands):
        command = commands[name]
        if getattr(command, "hidden", False) or name in NESTED_WORDS:
            continue
        help_text = str(getattr(command, "help", "") or "").strip()
        rows.append((name, help_text.splitlines()[0] if help_text else ""))
    return rows


def brand() -> None:
    """Logo, tagline and where we are; printed on entry and by ``clear``."""
    console.print(logo())
    console.print(
        Text.assemble(
            (TAGLINE, "italic"),
            (f"{DOT}v{mabat.__version__}{DOT}{_platform.node()} ({PLATFORM_NAME})", "dim"),
        )
    )
    console.print()


def banner(app: typer.Typer) -> None:
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold cyan", no_wrap=True)
    table.add_column()
    for name, help_text in _commands(app):
        table.add_row(name, Text(help_text))
    table.add_row("help", "Show this list.")
    table.add_row("clear", "Clear the screen.")
    table.add_row("quit", "Leave interactive mode (also: exit, q, Ctrl+D).")
    console.print(table)
    console.print(
        Text.assemble(
            ("sections: ", "dim"),
            ", ".join((*mabat.section_names(), "snapshot")),
            ("  -  a bare section name means 'show <section>'", "dim"),
        )
    )
    report = mabat.health()
    if not report.ok:
        missing = ", ".join(p.name for p in report.providers if p.required and not p.available)
        console.print(Text(f"! core providers missing: {missing} - run 'health'", style="yellow"))


def run_line(app: typer.Typer, line: str) -> int:
    """Run one command line through the app; never raises, returns its exit status."""
    try:
        args = shlex.split(line)
    except ValueError as exc:
        error_console.print(f"[red]could not parse that line:[/red] {exc}")
        return 2
    if not args:
        return 0
    if args[0] in mabat.section_names():  # 'snapshot' is a command in its own right
        args = ["show", *args]
    try:
        result = app(args, prog_name="mabat", standalone_mode=False)
    except typer.Abort:
        console.print(Text("aborted", style="dim"))
        return 1
    except Exception as exc:  # usage errors and anything else: report, keep the session alive
        show = getattr(exc, "show", None)  # typer's usage errors know how to print themselves
        if callable(show):
            show()
        else:
            error_console.print(f"[red]{type(exc).__name__}:[/red] {exc}")
        code = getattr(exc, "exit_code", 1)
        return int(code) if isinstance(code, int) else 1
    return result if isinstance(result, int) else 0


def repl(app: typer.Typer) -> None:
    brand()
    banner(app)
    while True:
        try:
            line = console.input(PROMPT)
        except EOFError:
            console.print()
            break
        except KeyboardInterrupt:
            console.print(Text("\n(type quit to leave)", style="dim"))
            continue
        words = line.strip().split(maxsplit=1)
        word = words[0].lower() if words else ""
        if word in EXIT_WORDS:
            break
        if word in HELP_WORDS:
            banner(app)
            continue
        if word in CLEAR_WORDS:
            console.clear()
            brand()
            continue
        if word in NESTED_WORDS:
            console.print(Text("already in interactive mode", style="dim"))
            continue
        run_line(app, line)
    console.print(Text("bye", style="dim"))
