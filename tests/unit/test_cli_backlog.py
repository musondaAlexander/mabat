"""Sprint 8: redaction, watch --log + history, speedtest."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

import mabat
from mabat._shared import platform as plat
from mabat._shared.models import ProblemKind, Problems, Section
from mabat._shared.redact import MASK, redact
from mabat.cli.app import app
from mabat.cli.history import read_history
from mabat.sections.network import Address, Counters, Interface, NetworkReport
from mabat.sections.speedtest import SpeedtestReport, read_speedtest

runner = CliRunner()


# --- redaction ---------------------------------------------------------------------------


def _network_section() -> Section[NetworkReport]:
    counters = Counters(1, 2, 3, 4, 0, 0, 0, 0)
    iface = Interface(
        "eth0",
        True,
        1000,
        1500,
        "full",
        False,
        (
            Address("ipv4", "192.168.1.10", "255.255.255.0", None),
            Address("mac", "00-11-22", None, None),
        ),
        counters,
        None,
    )
    report = NetworkReport("box", "192.168.1.10", (iface,), counters, None, None)
    return Section("network", datetime(2026, 1, 1, tzinfo=UTC), report)


def test_redact_masks_configured_keys_and_keeps_everything_else() -> None:
    masked = redact(_network_section())
    assert masked.data is not None
    assert masked.data.hostname == MASK and masked.data.outbound_ip == MASK
    iface = masked.data.interfaces[0]
    assert iface.name == "eth0"  # interface names are not identifying
    assert all(a.address == MASK for a in iface.addresses)
    assert iface.addresses[0].netmask == "255.255.255.0"  # only listed keys are touched
    assert masked.available and masked.name == "network"


def test_redact_is_a_copy_and_accepts_custom_keys() -> None:
    original = _network_section()
    masked = redact(original, keys=["name"])
    assert original.data is not None and original.data.hostname == "box"  # untouched
    assert masked.name == MASK  # a custom key list applies to whatever it names
    assert masked.data is not None and masked.data.hostname == "box"


def test_redact_walks_dicts_lists_and_leaves_scalars() -> None:
    payload = {"hostname": "box", "nested": [{"serial": "SN1", "size": 3}], "n": 1}
    assert redact(payload) == {"hostname": MASK, "nested": [{"serial": MASK, "size": 3}], "n": 1}
    assert redact(42) == 42


def test_cli_redact_flag_on_show_snapshot_and_connections() -> None:
    payload = json.loads(runner.invoke(app, ["show", "network", "--json", "--redact"]).output)
    assert payload["data"]["hostname"] == MASK
    payload = json.loads(
        runner.invoke(app, ["snapshot", "--json", "--only", "memory", "--redact"]).output
    )
    assert payload["hostname"] == MASK
    result = runner.invoke(app, ["connections", "--json", "--redact"])
    payload = json.loads(result.output)
    if payload["available"] and payload["data"]["connections"]:
        assert payload["data"]["connections"][0]["local_address"] == MASK


def test_privacy_guard_keys_and_redaction_keys_do_not_overlap() -> None:
    from tests.guards.test_privacy import FORBIDDEN_KEYS

    assert not (mabat.settings().redaction_keys & FORBIDDEN_KEYS)


# --- watch --log / history ----------------------------------------------------------------


def test_watch_log_appends_ndjson_and_history_replays_it(tmp_path: Path) -> None:
    log = tmp_path / "mem.ndjson"
    for _ in range(2):
        result = runner.invoke(
            app, ["watch", "memory", "-n", "2", "-i", "0.1", "--log", str(log), "--redact"]
        )
        assert result.exit_code == 0, result.output
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 4  # appended, not truncated
    assert all(json.loads(line)["name"] == "memory" for line in lines)

    history = read_history(log)
    assert len(history.frames) == 4 and history.label == "RAM %"
    assert history.minimum is not None and history.minimum <= history.maximum  # type: ignore[operator]

    result = runner.invoke(app, ["history", str(log)])
    assert result.exit_code == 0, result.output
    assert "RAM %" in result.output and "4 readings" in result.output

    payload = json.loads(runner.invoke(app, ["history", str(log), "--json"]).output)
    assert len(payload["frames"]) == 4


def test_history_handles_snapshots_bad_lines_and_missing_files(tmp_path: Path) -> None:
    log = tmp_path / "snap.ndjson"
    result = runner.invoke(
        app, ["watch", "snapshot", "-n", "1", "-i", "0.1", "--only", "cpu", "--json"]
    )
    log.write_text(result.output, encoding="utf-8")
    history = read_history(log)
    assert history.frames[0].target == "snapshot" and history.label == "cpu %"

    bad = tmp_path / "bad.ndjson"
    bad.write_text('{"name": "memory"}\nnot json\n', encoding="utf-8")
    with pytest.raises(ValueError, match=r"bad.ndjson:2"):
        read_history(bad)
    assert runner.invoke(app, ["history", str(bad)]).exit_code == 2
    assert runner.invoke(app, ["history", str(tmp_path / "nope.ndjson")]).exit_code == 2

    empty = tmp_path / "empty.ndjson"
    empty.write_text("", encoding="utf-8")
    assert "no readings" in runner.invoke(app, ["history", str(empty)]).output


# --- speedtest --------------------------------------------------------------------------------


def _fake_speedtest(*, fail: bool = False) -> SimpleNamespace:
    class FakeTest:
        def __init__(self, secure: bool = False) -> None:
            self.results = SimpleNamespace(
                download=93_400_000.0,
                upload=21_000_000.0,
                ping=12.3,
                server={
                    "name": "Lusaka",
                    "sponsor": "ISP",
                    "country": "Zambia",
                    "host": "h",
                    "d": 3.2,
                    "latency": 12.3,
                },
                client={"ip": "203.0.113.9", "isp": "ISP"},
            )

        def get_best_server(self) -> None:
            if fail:
                raise ConnectionError("no route")

        def download(self) -> float:
            return 0.0

        def upload(self) -> float:
            return 0.0

    return SimpleNamespace(Speedtest=FakeTest)


def test_read_speedtest_maps_results() -> None:
    problems = Problems()
    report = read_speedtest(_fake_speedtest(), problems)
    assert isinstance(report, SpeedtestReport)
    assert (report.download_bps, report.upload_bps, report.ping_ms) == (
        93_400_000.0,
        21_000_000.0,
        12.3,
    )
    assert report.server is not None and report.server.country == "Zambia"
    assert report.server.distance_km == 3.2
    assert report.public_ip == "203.0.113.9" and report.isp == "ISP"
    assert not problems


def test_read_speedtest_failure_is_a_problem() -> None:
    problems = Problems()
    assert read_speedtest(_fake_speedtest(fail=True), problems) is None
    assert problems.freeze()[0].kind is ProblemKind.BACKEND_ERROR
    assert "no route" in problems.freeze()[0].detail


def test_speedtest_command_with_fake_module(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plat, "optional_import", lambda name: _fake_speedtest())
    result = runner.invoke(app, ["speedtest"])
    assert result.exit_code == 0, result.output
    assert "93.4 Mbit/s" in result.output and "Zambia" in result.output

    payload = json.loads(runner.invoke(app, ["speedtest", "--json", "--redact"]).output)
    assert payload["data"]["public_ip"] == MASK and payload["data"]["isp"] == "ISP"


def test_speedtest_missing_package(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plat, "optional_import", lambda name: None)
    result = runner.invoke(app, ["speedtest"])
    assert result.exit_code == 1 and "speedtest-cli" in result.output


def test_speedtest_is_not_a_snapshot_section() -> None:
    assert "speedtest" not in mabat.section_names()
