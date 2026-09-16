from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

import mabat
from mabat import _health as health_module
from mabat.cli.app import app

runner = CliRunner()


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert mabat.__version__ in result.output


def test_health_table() -> None:
    result = runner.invoke(app, ["health"])
    assert result.exit_code == 0
    assert "psutil" in result.output
    assert "core providers available" in result.output


def test_health_json_is_parseable() -> None:
    result = runner.invoke(app, ["health", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.output)["ok"] is True


def test_health_exit_status_reflects_core_availability(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health_module, "optional_import", lambda module: None)
    result = runner.invoke(app, ["health"])
    assert result.exit_code == 1


def test_no_arguments_prints_help() -> None:
    result = runner.invoke(app, [])
    assert "Usage" in result.output


def test_show_cpu_and_memory_render_tables() -> None:
    for name, marker in (("cpu", "cores"), ("memory", "RAM")):
        result = runner.invoke(app, ["show", name])
        assert result.exit_code == 0, result.output
        assert marker in result.output


def test_show_json_is_the_library_payload() -> None:
    result = runner.invoke(app, ["show", "memory", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["name"] == "memory"
    assert set(payload) == {"name", "collected_at", "available", "data", "problems"}


def test_show_unknown_section_exits_2() -> None:
    result = runner.invoke(app, ["show", "nope"])
    assert result.exit_code == 2
    assert "unknown section" in result.output
    assert "cpu" in result.output


def test_show_unavailable_section_exits_1(monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import UTC, datetime

    from mabat._shared.models import Section

    def empty() -> Section[None]:
        return Section(name="memory", collected_at=datetime(2026, 1, 1, tzinfo=UTC), data=None)

    monkeypatch.setattr(mabat, "collectors", lambda: {"memory": empty})
    result = runner.invoke(app, ["show", "memory"])
    assert result.exit_code == 1
    assert "unavailable" in result.output


def test_watch_json_emits_one_document_per_line() -> None:
    result = runner.invoke(app, ["watch", "memory", "--json", "-n", "2", "-i", "0.1"])
    assert result.exit_code == 0, result.output
    lines = [line for line in result.output.splitlines() if line.strip()]
    assert len(lines) == 2
    assert all(json.loads(line)["name"] == "memory" for line in lines)


def test_watch_live_renders_and_stops_after_count() -> None:
    result = runner.invoke(app, ["watch", "cpu", "-n", "1", "-i", "0.1"])
    assert result.exit_code == 0, result.output
    assert "mabat watch" in result.output
    assert "core" in result.output


def test_watch_unknown_section_exits_2() -> None:
    assert runner.invoke(app, ["watch", "nope", "-n", "1"]).exit_code == 2


def test_watch_rejects_bad_interval() -> None:
    assert runner.invoke(app, ["watch", "cpu", "-i", "0"]).exit_code != 0


def test_watch_ctrl_c_stops_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import UTC, datetime

    from mabat._shared.models import Section

    calls = 0

    def interrupted() -> Section[None]:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise KeyboardInterrupt
        return Section(name="memory", collected_at=datetime(2026, 1, 1, tzinfo=UTC), data=None)

    monkeypatch.setattr(mabat, "collectors", lambda: {"memory": interrupted})
    result = runner.invoke(app, ["watch", "memory", "-i", "0.1"])
    assert result.exit_code == 0
    assert "stopped at" in result.output


def test_ticks_respects_count_and_spacing() -> None:
    import time

    from mabat.cli.app import _ticks

    stamps: list[float] = []

    def collect() -> object:
        stamps.append(time.monotonic())
        return object()

    readings = list(_ticks(collect, interval=0.05, count=3))
    assert len(readings) == 3
    assert stamps[-1] - stamps[0] >= 0.09


def test_show_system_and_storage_render_tables() -> None:
    for name, marker in (("system", "Processes"), ("storage", "Partitions")):
        result = runner.invoke(app, ["show", name])
        assert result.exit_code == 0, result.output
        assert marker in result.output


# --- interactive mode --------------------------------------------------------------------


def _interactive(script: str) -> str:
    result = runner.invoke(app, ["cli"], input=script)
    assert result.exit_code == 0, result.output
    return result.output


def test_cli_runs_commands_until_quit() -> None:
    output = _interactive("show memory\nquit\n")
    assert "interactive" in output
    assert "RAM" in output
    assert output.rstrip().endswith("bye")


def test_cli_bare_section_name_means_show() -> None:
    assert "cores" in _interactive("cpu\nq\n")


def test_cli_survives_unknown_commands_and_bad_quoting() -> None:
    output = _interactive('bogus\nshow "unterminated\nshow nope\nversion\nexit\n')
    assert "No such command" in output
    assert "could not parse" in output
    assert "unknown section" in output
    assert mabat.__version__ in output  # the session kept going


def test_cli_help_and_nested_guard() -> None:
    output = _interactive("help\ncli\nshell\nquit\n")
    assert output.count("Leave interactive mode") == 2  # banner at start + help
    assert output.count("already in interactive mode") == 2


def test_cli_end_of_input_exits_cleanly() -> None:
    assert _interactive("version\n").rstrip().endswith("bye")


def test_cli_shell_alias_is_hidden_but_works() -> None:
    result = runner.invoke(app, ["shell"], input="quit\n")
    assert result.exit_code == 0
    assert "shell" not in runner.invoke(app, ["--help"]).output


def test_run_line_exit_statuses() -> None:
    from mabat.cli.repl import run_line

    assert run_line(app, "") == 0
    assert run_line(app, "version") == 0
    assert run_line(app, "show nope") == 2
    assert run_line(app, "bogus") == 2
    assert run_line(app, 'show "x') == 2


def test_show_gpu_and_sensors_do_not_crash() -> None:
    for name in ("gpu", "sensors"):
        result = runner.invoke(app, ["show", name])
        assert result.exit_code in (0, 1), result.output  # 1 = honestly unavailable here
        assert "Traceback" not in result.output


def test_show_network_and_connections_command() -> None:
    result = runner.invoke(app, ["show", "network"])
    assert result.exit_code == 0, result.output
    assert "Interfaces" in result.output and "outbound ip" in result.output

    result = runner.invoke(app, ["connections"])
    assert result.exit_code in (0, 1), result.output
    assert "Traceback" not in result.output
    if result.exit_code == 0:
        assert "sockets" in result.output

    result = runner.invoke(app, ["connections", "--json"])
    payload = json.loads(result.output)
    assert payload["name"] == "connections"


# --- snapshot ---------------------------------------------------------------------------------


def test_snapshot_overview_and_json() -> None:
    result = runner.invoke(app, ["snapshot", "--only", "cpu,memory"])
    assert result.exit_code == 0, result.output
    assert "section" in result.output and "skipped" in result.output
    assert "ok" in result.output or "partial" in result.output

    result = runner.invoke(app, ["snapshot", "--json", "--only", "memory", "--skip", "cpu"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["memory"]["available"] is True
    assert payload["cpu"]["problems"][0]["kind"] == "skipped"
    assert set(mabat.section_names()) <= set(payload)


def test_snapshot_rejects_unknown_selection() -> None:
    result = runner.invoke(app, ["snapshot", "--only", "nope"])
    assert result.exit_code == 2
    assert "unknown section" in result.output


def test_snapshot_connections_flag_embeds_sockets() -> None:
    result = runner.invoke(app, ["snapshot", "--json", "--only", "network", "--connections"])
    payload = json.loads(result.output)
    network = payload["network"]
    if network["available"]:
        assert network["data"]["connections"] is not None


def test_show_and_watch_accept_snapshot_target() -> None:
    result = runner.invoke(app, ["show", "snapshot", "--json"])
    assert result.exit_code == 0 and "hostname" in json.loads(result.output)

    result = runner.invoke(app, ["watch", "snapshot", "-n", "1", "-i", "0.1", "--only", "memory"])
    assert result.exit_code == 0, result.output
    assert "mabat watch" in result.output and "memory" in result.output


def test_snapshot_exit_status_when_nothing_available(monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import UTC, datetime

    from mabat import _snapshot
    from mabat._shared.models import Section

    names = mabat.section_names()

    def empty(**kwargs: object) -> Section[None]:
        return Section(name="x", collected_at=datetime(2026, 1, 1, tzinfo=UTC), data=None)

    monkeypatch.setattr(_snapshot, "collectors", lambda: dict.fromkeys(names, empty))
    result = runner.invoke(app, ["snapshot"])
    assert result.exit_code == 1
    assert "unavailable" in result.output


def test_cli_banner_warns_when_core_provider_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    from mabat import _health as health_module

    monkeypatch.setattr(health_module, "optional_import", lambda module: None)
    output = _interactive("quit\n")
    assert "core providers missing" in output and "psutil" in output


def test_cli_snapshot_word_runs_the_snapshot_command() -> None:
    output = _interactive("snapshot --only memory\nquit\n")
    assert "section" in output and "memory" in output


def test_python_dash_m_entry_point() -> None:
    import subprocess
    import sys

    completed = subprocess.run(
        [sys.executable, "-m", "mabat", "version"], capture_output=True, text=True, check=False
    )
    assert completed.returncode == 0
    assert mabat.__version__ in completed.stdout
