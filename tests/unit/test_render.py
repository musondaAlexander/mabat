from __future__ import annotations

from datetime import UTC, datetime

import pytest
from rich.console import Console

from mabat._shared.config import settings
from mabat._shared.models import Problem, ProblemKind, Section
from mabat.cli.render import common


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, "-"), (0, "0 B"), (1023, "1023 B"), (1536, "1.5 KiB"), (16 * 2**20, "16.0 MiB")],
)
def test_fmt_bytes(value: int | None, expected: str) -> None:
    assert common.fmt_bytes(value) == expected


def test_fmt_bytes_precision_zero() -> None:
    assert common.fmt_bytes(16 * 2**20, precision=0) == "16 MiB"


@pytest.mark.parametrize(
    ("value", "mhz", "expected"),
    [
        (None, False, "-"),
        (3_294_000_000, False, "3.29 GHz"),
        (2011.0, True, "2.01 GHz"),
        (800.0, True, "800 MHz"),
    ],
)
def test_fmt_hz(value: float | None, mhz: bool, expected: str) -> None:
    assert common.fmt_hz(value, mhz=mhz) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, "-"), (59, "0m 59s"), (3_661, "1h 01m 01s"), (90_000, "1d 01h 00m")],
)
def test_fmt_seconds(value: float | None, expected: str) -> None:
    assert common.fmt_seconds(value) == expected


def test_pct_text_uses_thresholds() -> None:
    limits = settings().thresholds
    assert common.pct_text(limits.warn_percent - 1).style == "green"
    assert common.pct_text(limits.warn_percent).style == "yellow"
    assert common.pct_text(limits.critical_percent).style == "bold red"
    assert common.pct_text(None).plain == "-"


def test_bar_is_proportional_and_clamped() -> None:
    assert common.bar(50, width=10).plain == common.FILLED * 5 + common.EMPTY * 5
    assert common.bar(150, width=4).plain == common.FILLED * 4
    assert common.bar(-5, width=4).plain == common.EMPTY * 4


def test_render_problems_lists_each_problem(monkeypatch: pytest.MonkeyPatch) -> None:
    capture = Console(record=True, width=120, force_terminal=False)
    monkeypatch.setattr(common, "console", capture)
    section: Section[int] = Section(
        name="x",
        collected_at=datetime(2026, 1, 1, tzinfo=UTC),
        data=None,
        problems=(Problem("nvml", ProblemKind.MISSING_DEPENDENCY, "pip install nvidia-ml-py"),),
    )
    common.render_problems(section)
    text = capture.export_text()
    assert "nvml [missing_dependency]" in text
    assert "pip install nvidia-ml-py" in text
