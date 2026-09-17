"""Line editing for interactive mode: completion tree and reader selection."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from prompt_toolkit.completion import CompleteEvent, NestedCompleter
from prompt_toolkit.document import Document

import mabat
from mabat.cli import prompt
from mabat.cli.app import app

HIDDEN = frozenset({"cli", "shell"})


def _complete(text: str) -> list[str]:
    completer = NestedCompleter.from_nested_dict(prompt.completion_tree(app, HIDDEN))
    return sorted(c.text for c in completer.get_completions(Document(text), CompleteEvent()))


def test_tree_lists_commands_sections_and_extra_words() -> None:
    top = _complete("")
    for word in ("show", "watch", "snapshot", "health", "config", "bench", "help", "quit", "clear"):
        assert word in top
    assert set(mabat.section_names()) <= set(top)
    assert "cli" not in top and "shell" not in top


def test_targets_complete_after_show_and_watch() -> None:
    assert _complete("show cp") == ["cpu"]
    assert "snapshot" in _complete("watch ")
    assert _complete("memory --") == _complete("show memory --")  # bare section == show


def test_flags_are_filtered_to_the_target() -> None:
    assert _complete("show cpu --") == ["--json", "--redact", "--sample"]
    assert "--top" in _complete("show system --") and "--counters" not in _complete(
        "show system --"
    )
    assert "--all" in _complete("show network --") and "--all" not in _complete("show gpu --")
    snapshot_flags = _complete("watch snapshot --")
    assert {"--only", "--skip", "--top", "--counters", "--interval", "--log"} <= set(snapshot_flags)
    assert "--all" not in snapshot_flags


def test_non_target_commands_offer_their_own_flags() -> None:
    assert _complete("connections --") == ["--json", "--kind", "--redact"]
    assert "--only" in _complete("bench --")


def test_plain_reader_when_not_a_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("x\n"))
    read, mode = prompt.line_reader(app, "> ", hidden=HIDDEN)
    assert mode == "plain"
    assert read() == "x"  # the plain reader is console.input, fed from stdin


def test_plain_reader_when_prompt_toolkit_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    class Tty(io.StringIO):
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr("sys.stdin", Tty())
    monkeypatch.setattr("sys.stdout", Tty())
    import builtins

    real_import = builtins.__import__

    def no_prompt_toolkit(name: str, *args: object, **kwargs: object) -> object:
        if name.startswith("prompt_toolkit"):
            raise ImportError(name)
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", no_prompt_toolkit)
    _, mode = prompt.line_reader(app, "> ", hidden=HIDDEN)
    assert mode == "plain"


def test_history_file_lives_in_home() -> None:
    assert Path.home() / ".mabat_history" == prompt.HISTORY_FILE


def test_prompt_session_reads_lines_headlessly() -> None:
    from prompt_toolkit.history import InMemoryHistory
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    with create_pipe_input() as pipe:
        session = prompt.make_session(
            app, HIDDEN, input=pipe, output=DummyOutput(), history=InMemoryHistory()
        )
        pipe.send_text("show cpu --json\r")
        assert session.prompt() == "show cpu --json"
        assert list(session.history.get_strings()) == ["show cpu --json"]
        pipe.send_text("\x04")  # Ctrl+D
        with pytest.raises(EOFError):
            session.prompt()
