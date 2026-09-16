from __future__ import annotations

import json

import mabat
from mabat import _snapshot as snapshot_module
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
