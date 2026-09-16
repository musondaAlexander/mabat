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
