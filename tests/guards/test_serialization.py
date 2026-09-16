"""Serialisation guard: one outward path, and nothing internal leaks through it (AGENT.md §1.2).

S1  Every registered section serialises to valid JSON through ``to_json``.
S2  Every section payload has exactly the contract keys; every problem has source/kind/detail.
S3  The serialiser rejects foreign objects (psutil namedtuples, handles) instead of guessing.
S4  Every public model is a *frozen* dataclass - consumers get values, not mutable state.
"""

from __future__ import annotations

import dataclasses
import importlib
import json
import pkgutil
from collections import namedtuple
from types import ModuleType

import pytest

import mabat
from mabat import _snapshot
from mabat._shared.serialize import to_dict, to_json

SECTION_KEYS = {"name", "collected_at", "available", "data", "problems"}
PROBLEM_KEYS = {"source", "kind", "detail"}


def _collectors() -> list[tuple[str, object]]:
    return list(_snapshot.collectors().items())


@pytest.mark.parametrize(("name", "collect"), _collectors(), ids=[n for n, _ in _collectors()])
def test_s1_s2_section_payload_contract(name: str, collect: object) -> None:
    assert callable(collect)
    payload = json.loads(to_json(collect()))
    assert set(payload) == SECTION_KEYS, f"{name}: payload keys {sorted(payload)}"
    assert payload["name"] == name
    assert isinstance(payload["available"], bool)
    assert payload["available"] == (payload["data"] is not None)
    for problem in payload["problems"]:
        assert set(problem) == PROBLEM_KEYS
        assert problem["source"] and problem["detail"]


def test_s1_snapshot_and_health_serialise() -> None:
    snapshot_payload = json.loads(to_json(mabat.snapshot()))
    assert {"collected_at", "hostname", "platform"} <= set(snapshot_payload)
    for name in mabat.section_names():
        assert set(snapshot_payload[name]) == SECTION_KEYS
    health_payload = json.loads(to_json(mabat.health()))
    assert {"ok", "providers"} <= set(health_payload)


def test_s3_foreign_objects_are_rejected() -> None:
    Freq = namedtuple("Freq", "current min max")
    with pytest.raises(TypeError):
        to_dict(Freq(1.0, 0.0, 3.0))

    class NvmlHandle:
        pass

    with pytest.raises(TypeError):
        to_dict(NvmlHandle())
    with pytest.raises(TypeError):
        to_dict({"gpu": NvmlHandle()})


def _library_modules() -> list[ModuleType]:
    """Every importable module in mabat except the CLI (which would pull in typer/rich)."""
    modules = [mabat]
    for info in pkgutil.walk_packages(mabat.__path__, prefix="mabat."):
        if info.name.startswith("mabat.cli"):
            continue
        modules.append(importlib.import_module(info.name))
    return modules


def test_s4_every_public_model_is_a_frozen_dataclass() -> None:
    offenders = []
    for module in _library_modules():
        for attr_name, obj in vars(module).items():
            if not isinstance(obj, type) or not dataclasses.is_dataclass(obj):
                continue
            if obj.__module__ != module.__name__:
                continue  # re-export; checked where it is defined
            params = getattr(obj, "__dataclass_params__", None)
            if params is None or not params.frozen:
                offenders.append(f"{module.__name__}.{attr_name}")
    assert not offenders, "mutable dataclasses in the public library: " + ", ".join(offenders)
