from __future__ import annotations

import json
import math
from collections import namedtuple
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import PurePosixPath

import pytest

from mabat._shared.models import ProblemKind, Section
from mabat._shared.serialize import flatten, to_dict, to_json


class Colour(Enum):
    RED = "red"


@dataclass(frozen=True)
class Inner:
    value: float
    when: datetime


@dataclass(frozen=True)
class Outer:
    name: str
    inner: Inner
    items: tuple[int, ...]
    kind: ProblemKind
    colour: Colour
    path: PurePosixPath
    mapping: dict[str, int | None]


def test_to_dict_handles_every_supported_type() -> None:
    when = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)
    outer = Outer(
        name="x",
        inner=Inner(1.5, when),
        items=(1, 2),
        kind=ProblemKind.NOT_PRESENT,
        colour=Colour.RED,
        path=PurePosixPath("/dev/sda"),
        mapping={"a": 1, "b": None},
    )
    assert to_dict(outer) == {
        "name": "x",
        "inner": {"value": 1.5, "when": "2026-09-16T12:00:00+00:00"},
        "items": [1, 2],
        "kind": "not_present",
        "colour": "red",
        "path": "/dev/sda",
        "mapping": {"a": 1, "b": None},
    }


def test_section_serialises_with_computed_available_flag() -> None:
    section: Section[int] = Section(
        name="cpu", collected_at=datetime(2026, 1, 1, tzinfo=UTC), data=None
    )
    payload = to_dict(section)
    assert isinstance(payload, dict)
    assert set(payload) == {"name", "collected_at", "data", "problems", "available"}
    assert payload["available"] is False


def test_non_finite_floats_become_null() -> None:
    assert to_dict([math.nan, math.inf, 1.0]) == [None, None, 1.0]
    assert json.loads(to_json({"x": math.nan})) == {"x": None}


def test_namedtuples_are_rejected() -> None:
    Freq = namedtuple("Freq", "current min max")
    with pytest.raises(TypeError, match="namedtuple"):
        to_dict(Freq(1.0, 0.0, 3.0))


def test_foreign_objects_are_rejected() -> None:
    class Handle:
        pass

    with pytest.raises(TypeError, match="not serialisable"):
        to_dict(Handle())


def test_to_json_is_valid_json_with_indent() -> None:
    text = to_json({"a": [1, 2]}, indent=2)
    assert json.loads(text) == {"a": [1, 2]}
    assert "\n" in text


def test_flatten_produces_dotted_keys() -> None:
    inner = Inner(2.0, datetime(2026, 1, 1, tzinfo=UTC))
    assert flatten({"cpu": {"usage": inner, "cores": [6, 12]}}) == {
        "cpu.usage.value": 2.0,
        "cpu.usage.when": "2026-01-01T00:00:00+00:00",
        "cpu.cores.0": 6,
        "cpu.cores.1": 12,
    }
