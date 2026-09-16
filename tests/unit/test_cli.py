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

    readings = list(_ticks(collect, interval=0.05, count=3))  # type: ignore[arg-type]
    assert len(readings) == 3
    assert stamps[-1] - stamps[0] >= 0.09


def test_show_system_and_storage_render_tables() -> None:
    for name, marker in (("system", "Processes"), ("storage", "Partitions")):
        result = runner.invoke(app, ["show", name])
        assert result.exit_code == 0, result.output
        assert marker in result.output
