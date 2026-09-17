from __future__ import annotations

import json

import pytest

import mabat
from mabat import _snapshot as snapshot_module
from mabat._shared.models import ProblemKind, Section
from mabat._shared.serialize import to_json


def test_snapshot_collects_every_registered_section() -> None:
    snap = mabat.snapshot()
    assert set(mabat.sections_of(snap)) == set(mabat.section_names())
    assert snap.hostname
    for name, section in mabat.sections_of(snap).items():
        assert section.name == name


def test_snapshot_serialises_cleanly() -> None:
    payload = json.loads(to_json(mabat.snapshot()))
    assert {"collected_at", "hostname", "platform"} <= set(payload)


def test_collectors_follow_field_order() -> None:
    assert tuple(snapshot_module.collectors()) == mabat.section_names()


def test_only_and_skip_select_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    names = mabat.section_names()

    def fake_collectors() -> dict[str, object]:
        def make(name: str) -> object:
            def collect(**kwargs: object) -> Section[str]:
                calls.append(name)
                return _section(name)

            return collect

        return {name: make(name) for name in names}

    monkeypatch.setattr(snapshot_module, "collectors", fake_collectors)
    snap = mabat.snapshot(only=["cpu", "memory", "gpu"], skip=["gpu"])
    assert calls == ["cpu", "memory"]
    assert snap.cpu.available and snap.memory.available
    assert not snap.gpu.available and snap.gpu.problems[0].kind is ProblemKind.SKIPPED
    assert not snap.system.available and snap.system.problems[0].kind is ProblemKind.SKIPPED
    assert set(mabat.sections_of(snap)) == set(names)  # shape never changes


def test_options_are_routed_only_to_declaring_collectors(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, dict[str, object]] = {}
    names = mabat.section_names()

    def fake_collectors() -> dict[str, object]:
        def make(name: str) -> object:
            def collect(**kwargs: object) -> Section[str]:
                seen[name] = kwargs
                return _section(name)

            return collect

        return {name: make(name) for name in names}

    monkeypatch.setattr(snapshot_module, "collectors", fake_collectors)
    mabat.snapshot(connections=True)
    assert seen["network"] == {"connections": True}
    assert all(kwargs == {} for name, kwargs in seen.items() if name != "network")


def test_snapshot_rejects_unknown_sections_and_options() -> None:
    with pytest.raises(ValueError, match="unknown section"):
        mabat.snapshot(only=["nope"])
    with pytest.raises(ValueError, match="unknown section"):
        mabat.snapshot(skip=["nope"])
    with pytest.raises(TypeError, match="unknown snapshot option"):
        mabat.snapshot(bogus=1)


def test_problems_of_flattens_every_section(monkeypatch: pytest.MonkeyPatch) -> None:
    names = mabat.section_names()
    monkeypatch.setattr(
        snapshot_module,
        "collectors",
        lambda: {name: (lambda n=name, **kw: _section(n)) for name in names},
    )
    snap = mabat.snapshot(only=["cpu"])
    flattened = mabat.problems_of(snap)
    assert {name for name, _ in flattened} == set(names) - {"cpu"}
    assert all(problem.kind is ProblemKind.SKIPPED for _, problem in flattened)


def test_snapshot_options_lists_declared_options() -> None:
    assert mabat.snapshot_options() == {
        "sample_seconds": ("cpu",),
        "top_n": ("system",),
        "process_sample_seconds": ("system",),
        "all_partitions": ("storage",),
        "smart": ("storage",),
        "counters": ("gpu",),
        "connections": ("network",),
    }


def test_snapshot_routes_every_declared_option() -> None:
    snap = mabat.snapshot(only=["cpu", "system", "storage"], sample_seconds=0, top_n=0, smart=False)
    assert snap.cpu.data is not None and snap.cpu.data.usage is not None
    assert snap.cpu.data.usage.sample_seconds == 0.0
    assert snap.system.data is not None and snap.system.data.processes is not None
    assert snap.system.data.processes.top_n == 0
    assert snap.storage.data is not None and snap.storage.data.smart is None


def _section(name: str) -> Section[str]:
    from datetime import UTC, datetime

    return Section(name=name, collected_at=datetime(2026, 1, 1, tzinfo=UTC), data="ok")
