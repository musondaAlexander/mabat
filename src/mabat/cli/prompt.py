"""Line editing for interactive mode: history, auto-suggest and tab completion.

Built on prompt_toolkit when both stdin and stdout are terminals; otherwise (tests, pipes,
missing package) a plain ``input()`` reader is returned so the loop behaves identically.
The completion tree is derived from the Typer app, so new commands and flags complete
without touching this module.
"""

from __future__ import annotations

import contextlib
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import typer

import mabat
from mabat.cli.render.common import console
from mabat.cli.targets import FLAGS, SNAPSHOT

HISTORY_FILE = Path.home() / ".mabat_history"
EXTRA_WORDS = ("help", "quit", "exit", "clear")
TARGET_COMMANDS = ("show", "watch")


_TARGET_ONLY = {"--only": SNAPSHOT, "--skip": SNAPSHOT, "--all": "network"}


def _applies(flag: str, target: str) -> bool:
    """Whether a flag makes sense after ``show <target>`` / ``watch <target>``."""
    if flag in _TARGET_ONLY:
        return target == _TARGET_ONLY[flag]
    options = FLAGS.get(flag)
    if options is None:
        return True  # generic: --json, --redact, --interval ...
    if target == SNAPSHOT:
        return True
    accepted = mabat.snapshot_options()
    return any(target in accepted.get(option, ()) for option in options)


def completion_tree(app: typer.Typer, hidden: frozenset[str] = frozenset()) -> dict[str, Any]:
    """``{command: {argument: {--flag: None}}}`` for prompt_toolkit's NestedCompleter."""
    group = typer.main.get_command(app)
    commands: dict[str, Any] = getattr(group, "commands", {})
    targets = (*mabat.section_names(), SNAPSHOT)
    tree: dict[str, Any] = {}
    for name, command in commands.items():
        if getattr(command, "hidden", False) or name in hidden:
            continue
        flags: dict[str, None] = {}
        for param in getattr(command, "params", []):
            for opt in getattr(param, "opts", []):
                if str(opt).startswith("--"):
                    flags[str(opt)] = None
        if name in TARGET_COMMANDS:
            tree[name] = {
                target: {flag: None for flag in flags if _applies(flag, target)}
                for target in targets
            }
        else:
            tree[name] = flags or None
    show_flags = tree.get("show") or {}
    for section in mabat.section_names():  # a bare section name means `show <section>`
        tree[section] = dict(show_flags.get(section) or {}) or None
    for word in EXTRA_WORDS:
        tree[word] = None
    return tree


def _plain_reader(prompt_markup: str) -> Callable[[], str]:
    return lambda: console.input(prompt_markup)


def make_session(
    app: typer.Typer, hidden: frozenset[str] = frozenset(), **session_kwargs: Any
) -> Any:
    """A configured prompt_toolkit ``PromptSession``. Raises ``ImportError`` without the
    package. ``session_kwargs`` (input/output/history) let tests drive it headlessly."""
    from prompt_toolkit import PromptSession
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.completion import NestedCompleter
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.history import FileHistory

    if "history" not in session_kwargs:
        # an unwritable home directory still gets line editing, just no persistence
        with contextlib.suppress(OSError):
            session_kwargs["history"] = FileHistory(str(HISTORY_FILE))
    return PromptSession(
        HTML("<b><ansicyan>mabat&gt;</ansicyan></b> "),
        auto_suggest=AutoSuggestFromHistory(),
        completer=NestedCompleter.from_nested_dict(completion_tree(app, hidden)),
        complete_while_typing=False,
        **session_kwargs,
    )


def line_reader(
    app: typer.Typer, prompt_markup: str, *, hidden: frozenset[str] = frozenset()
) -> tuple[Callable[[], str], str]:
    """(read_line, mode) where mode is ``"prompt_toolkit"`` or ``"plain"``.

    ``read_line`` raises ``EOFError`` on Ctrl+D and ``KeyboardInterrupt`` on Ctrl+C, in
    both modes, so the loop needs no special cases.
    """
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return _plain_reader(prompt_markup), "plain"
    try:
        session = make_session(app, hidden)
    except ImportError:
        return _plain_reader(prompt_markup), "plain"
    return session.prompt, "prompt_toolkit"
