"""Sprint 7: per-section flags, config, bench, session stats, branding, global flags."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from typer.testing import CliRunner

import mabat
from mabat._shared.models import Section
from mabat.cli import stats, targets
from mabat.cli.app import app
from mabat.sections.cpu import CpuReport, CpuUsage

runner = CliRunner()


# --- option routing ------------------------------------------------------------------------


def test_collector_options_only_include_flags_that_were_given() -> None:
    assert targets.collector_options() == {}
    assert targets.collector_options(sample=0.0) == {
        "sample_seconds": 0.0,
        "process_sample_seconds": 0.0,
    }
    assert targets.collector_options(top=3, no_smart=True, all_partitions=True) == {
        "top_n": 3,
        "smart": False,
        "all_partitions": True,
    }
    assert targets.collector_options(connections=True) == {"connections": True}


def test_every_flag_option_is_declared_by_some_section() -> None:
    accepted = mabat.snapshot_options()
    for flag, options in targets.FLAGS.items():
        assert any(option in accepted for option in options), flag


def test_show_routes_flags_to_the_section() -> None:
    result = runner.invoke(app, ["show", "system", "--top", "0", "--sample", "0", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["data"]["processes"]["top_n"] == 0

    result = runner.invoke(app, ["show", "storage", "--no-smart", "--json"])
    assert json.loads(result.output)["data"]["smart"] is None

    result = runner.invoke(app, ["show", "network", "--connections", "--json"])
    payload = json.loads(result.output)
    if payload["available"]:
        assert payload["data"]["connections"] is not None


def test_misapplied_flag_exits_2_and_names_the_right_sections() -> None:
    result = runner.invoke(app, ["show", "cpu", "--top", "3"])
    assert result.exit_code == 2
    assert "--top does not apply to 'cpu'" in result.output and "system" in result.output

    # --sample feeds cpu *and* system, so it is fine on either
    assert runner.invoke(app, ["show", "cpu", "--sample", "0"]).exit_code == 0
    assert runner.invoke(app, ["show", "system", "--sample", "0"]).exit_code == 0


def test_snapshot_routes_flags_everywhere() -> None:
    result = runner.invoke(
        app, ["snapshot", "--json", "--only", "cpu,system,storage", "--top", "0", "--no-smart"]
    )
    payload = json.loads(result.output)
    assert payload["system"]["data"]["processes"]["top_n"] == 0
    assert payload["storage"]["data"]["smart"] is None


def test_network_all_shows_hidden_interfaces() -> None:
    plain = runner.invoke(app, ["show", "network"]).output
    everything = runner.invoke(app, ["show", "network", "--all"]).output
    if "hidden:" in plain:
        assert "--all shows them" in plain
        assert "hidden:" not in everything


def test_connections_kind_validation() -> None:
    assert runner.invoke(app, ["connections", "--kind", "nope"]).exit_code == 2
    result = runner.invoke(app, ["connections", "--kind", "udp", "--json"])
    payload = json.loads(result.output)
    if payload["available"]:
        assert all(c["protocol"] == "udp" for c in payload["data"]["connections"])


# --- config / bench --------------------------------------------------------------------------


def test_config_lists_sources_and_effective_values() -> None:
    result = runner.invoke(app, ["config"])
    assert result.exit_code == 0, result.output
    assert "defaults" in result.output and "applied" in result.output
    assert "top_processes" in result.output

    payload = json.loads(runner.invoke(app, ["config", "--json"]).output)
    assert payload["sources"][0]["kind"] == "defaults"
    assert payload["settings"]["top_processes"] == 0  # the test conftest override


def test_resolve_settings_reports_each_source(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolved = mabat.resolve_settings()
    kinds = [s.kind for s in resolved.sources]
    assert kinds[0] == "defaults" and "local" in kinds
    assert all(s.applied for s in resolved.sources if s.kind in ("defaults", "local"))


def test_bench_command_reports_timings() -> None:
    result = runner.invoke(app, ["bench", "--only", "memory", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["timings"][0]["section"] == "memory"
    assert payload["timings"][0]["warm_seconds"] >= 0

    result = runner.invoke(app, ["bench", "--only", "memory"])
    assert "memory" in result.output and ("ok" in result.output or "over budget" in result.output)


# --- watch session stats ------------------------------------------------------------------------


def _cpu_section(percent: float) -> Section[CpuReport]:
    usage = CpuUsage(percent, (percent,), 0.0, None, None, None, None)
    return Section("cpu", datetime(2026, 1, 1, tzinfo=UTC), CpuReport(None, usage))


def test_headline_and_session_stats() -> None:
    session = stats.SessionStats()
    assert session.summary() is None
    for value in (10.0, 30.0, 20.0):
        session.add(stats.headline(_cpu_section(value)))
    assert session.count == 3 and session.minimum == 10.0 and session.maximum == 30.0
    assert session.mean == 20.0
    summary = session.summary()
    assert summary is not None and "cpu %: min 10.0" in summary and "3 frames" in summary
    session.add(None)  # unavailable frame: ignored
    assert session.count == 3

    empty: Section[CpuReport] = Section("cpu", datetime(2026, 1, 1, tzinfo=UTC), None)
    assert stats.headline(empty) is None


def test_watch_prints_session_line() -> None:
    result = runner.invoke(app, ["watch", "cpu", "-n", "2", "-i", "0.1", "--sample", "0"])
    assert result.exit_code == 0, result.output
    assert "session cpu %" in result.output


# --- branding and global flags ----------------------------------------------------------------


def test_interactive_mode_is_branded_and_clear_works() -> None:
    result = runner.invoke(app, ["cli"], input="clear\nquit\n")
    assert result.exit_code == 0, result.output
    assert "observe your machine" in result.output
    assert result.output.count("observe your machine") == 2  # entry + clear
    assert f"v{mabat.__version__}" in result.output
    assert "clear" in result.output  # listed in the banner


def test_global_no_color_and_width_flags() -> None:
    result = runner.invoke(app, ["--no-color", "--width", "60", "show", "memory"])
    assert result.exit_code == 0, result.output
    assert "\x1b[" not in result.output
    assert max(len(line) for line in result.output.splitlines()) <= 60


def test_completion_is_available() -> None:
    assert "--install-completion" in runner.invoke(app, ["--help"]).output
