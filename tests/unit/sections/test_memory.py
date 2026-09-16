from __future__ import annotations

import json
from collections import namedtuple
from types import SimpleNamespace
from typing import Any

import pytest

import mabat
from mabat._shared import platform as plat
from mabat._shared.models import ProblemKind, Problems
from mabat.sections.memory import collector

# Linux-shaped virtual memory (has the platform-specific buckets)
Virtual = namedtuple("Virtual", "total available percent used free active inactive buffers cached")
Swap = namedtuple("Swap", "total used free percent sin sout")


def _fake_psutil(**overrides: Any) -> SimpleNamespace:
    base = {
        "virtual_memory": lambda: Virtual(
            16_000, 8_000, 50.0, 7_000, 1_000, 3_000, 2_000, 500, 1_500
        ),
        "swap_memory": lambda: Swap(4_000, 1_000, 3_000, 25.0, 10, 20),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_virtual_and_swap_from_fake_psutil() -> None:
    problems = Problems()
    fake = _fake_psutil()
    virtual = collector.read_virtual(fake, problems)
    swap = collector.read_swap(fake, problems)
    assert virtual is not None and swap is not None
    assert (virtual.total_bytes, virtual.available_bytes, virtual.percent) == (16_000, 8_000, 50.0)
    assert virtual.other_bytes == {
        "active": 3_000,
        "inactive": 2_000,
        "buffers": 500,
        "cached": 1_500,
    }
    assert swap.swapped_in_bytes == 10 and swap.swapped_out_bytes == 20
    assert not problems


def test_memory_without_psutil(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plat, "optional_import", lambda name: None)
    section = mabat.memory()
    assert not section.available
    assert section.problems[0].kind is ProblemKind.MISSING_DEPENDENCY


def test_memory_partial_when_swap_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken() -> None:
        raise OSError("no pagefile")

    monkeypatch.setattr(plat, "optional_import", lambda name: _fake_psutil(swap_memory=broken))
    section = mabat.memory()
    assert section.available
    assert section.data is not None
    assert section.data.virtual is not None and section.data.swap is None
    assert section.problems[0].source == "psutil.swap_memory"


def test_memory_unavailable_when_both_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken() -> None:
        raise RuntimeError("hostile")

    fake = _fake_psutil(virtual_memory=broken, swap_memory=broken)
    monkeypatch.setattr(plat, "optional_import", lambda name: fake)
    section = mabat.memory()
    assert not section.available
    assert {p.source for p in section.problems} == {
        "psutil.virtual_memory",
        "psutil.swap_memory",
    }


def test_memory_on_this_machine_serialises() -> None:
    section = mabat.memory()
    assert section.available
    payload = json.loads(mabat.to_json(section))
    virtual = payload["data"]["virtual"]
    assert virtual["total_bytes"] > 0
    assert 0.0 <= virtual["percent"] <= 100.0
    assert virtual["available_bytes"] <= virtual["total_bytes"]
