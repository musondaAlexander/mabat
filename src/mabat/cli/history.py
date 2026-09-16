"""Replay NDJSON written by ``watch --log`` / ``watch --json``."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import RenderableType
from rich.table import Table
from rich.text import Text

from mabat.cli.render.common import DOT, assemble, heading
from mabat.cli.stats import SessionStats, headline

_ROWS_SHOWN = 200


@dataclass(frozen=True, slots=True)
class Frame:
    line: int
    collected_at: str
    target: str
    label: str | None
    value: float | None
    available: bool


@dataclass(frozen=True, slots=True)
class History:
    path: str
    frames: tuple[Frame, ...]
    first: str | None
    last: str | None
    label: str | None
    minimum: float | None
    mean: float | None
    maximum: float | None


def _target_name(payload: dict[str, Any]) -> str:
    if "hostname" in payload and "cpu" in payload:
        return "snapshot"
    return str(payload.get("name", "?"))


def _available(payload: dict[str, Any]) -> bool:
    if _target_name(payload) == "snapshot":
        return any(
            isinstance(section, dict) and section.get("available") for section in payload.values()
        )
    return bool(payload.get("available"))


def read_history(path: Path) -> History:
    """Parse a log file. Raises ``ValueError`` with the offending line on bad JSON."""
    frames: list[Frame] = []
    stats = SessionStats()
    with path.open(encoding="utf-8") as handle:
        for number, raw in enumerate(handle, start=1):
            text = raw.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{number}: not JSON ({exc.msg})") from None
            if not isinstance(payload, dict):
                raise ValueError(f"{path}:{number}: expected a JSON object")
            picked = headline(payload)
            stats.add(picked)
            frames.append(
                Frame(
                    line=number,
                    collected_at=str(payload.get("collected_at", "")),
                    target=_target_name(payload),
                    label=picked[0] if picked else None,
                    value=picked[1] if picked else None,
                    available=_available(payload),
                )
            )
    return History(
        path=str(path),
        frames=tuple(frames),
        first=frames[0].collected_at if frames else None,
        last=frames[-1].collected_at if frames else None,
        label=stats.label,
        minimum=stats.minimum if stats.count else None,
        mean=stats.mean if stats.count else None,
        maximum=stats.maximum if stats.count else None,
    )


def _stamp(value: str) -> str:
    try:
        return datetime.fromisoformat(value).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return value or "-"


def render_history(history: History) -> RenderableType:
    if not history.frames:
        return Text(f"{history.path}: no readings", style="dim")
    table = Table(show_edge=False, pad_edge=False, box=None, header_style="bold")
    table.add_column("#", justify="right", style="dim")
    table.add_column("collected")
    table.add_column("target", style="bold cyan")
    table.add_column(history.label or "headline", justify="right")
    table.add_column("status")
    for frame in history.frames[:_ROWS_SHOWN]:
        table.add_row(
            str(frame.line),
            _stamp(frame.collected_at),
            frame.target,
            f"{frame.value:.1f}" if frame.value is not None else "-",
            Text("ok", style="green") if frame.available else Text("unavailable", style="red"),
        )
    more = len(history.frames) - _ROWS_SHOWN
    note = Text(f"+{more} more (use --json)", style="dim") if more > 0 else None
    summary = None
    if history.label and history.minimum is not None:
        summary = Text(
            f"{history.label}: min {history.minimum:.1f}{DOT}avg {history.mean:.1f}"
            f"{DOT}max {history.maximum:.1f}{DOT}{len(history.frames)} readings",
            style="dim",
        )
    span = Text(
        f"{history.path}{DOT}{_stamp(history.first or '')} to {_stamp(history.last or '')}",
        style="dim",
    )
    return assemble(heading("History"), span, Text(""), table, note, Text(""), summary)
