"""Degradation guard: collectors never raise; missing backends become problems (AGENT.md §1.5).

D1  With every optional import absent and every external command missing, each collector
    still returns a Section and explains the gap.
D2  With a hostile backend (psutil / cpuinfo functions raising), each collector still
    returns a Section - data may be None or partial, but the call never propagates.
D3  ``run_collector`` itself keeps that promise for arbitrary exceptions.
"""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType
from typing import Any

import pytest

from mabat import _snapshot
from mabat._shared import platform as plat
from mabat._shared.models import ProblemKind, Problems, Section, run_collector

BACKENDS = ("psutil", "cpuinfo")


def _collectors() -> list[tuple[str, Callable[[], Section[Any]]]]:
    return list(_snapshot.collectors().items())


def _ids() -> list[str]:
    return [name for name, _ in _collectors()]


def _missing_command(*args: object, **kwargs: object) -> None:
    raise plat.CommandNotFoundError("simulated: executable not installed")


def _assert_well_formed(section: Section[Any], name: str) -> None:
    assert isinstance(section, Section)
    assert section.name == name
    assert section.available == (section.data is not None)
    for problem in section.problems:
        assert problem.source and problem.detail
        assert isinstance(problem.kind, ProblemKind)


@pytest.mark.parametrize(("name", "collect"), _collectors(), ids=_ids())
def test_d1_survives_missing_optional_dependencies_and_commands(
    name: str, collect: Callable[[], Section[Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(plat, "optional_import", lambda module: None)
    monkeypatch.setattr(plat, "command_available", lambda executable: False)
    monkeypatch.setattr(plat, "run_command", _missing_command)
    monkeypatch.setattr(plat, "run_powershell", _missing_command)
    _assert_well_formed(collect(), name)


def _make_hostile(module: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    def hostile(*args: object, **kwargs: object) -> None:
        raise RuntimeError(f"simulated {module.__name__} failure")

    for attr in dir(module):
        if attr.startswith("_"):
            continue
        if callable(getattr(module, attr)) and not isinstance(getattr(module, attr), type):
            monkeypatch.setattr(module, attr, hostile, raising=False)


@pytest.mark.parametrize(("name", "collect"), _collectors(), ids=_ids())
def test_d2_survives_hostile_backends(
    name: str, collect: Callable[[], Section[Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    for backend in BACKENDS:
        module = plat.optional_import(backend)
        if module is not None:
            _make_hostile(module, monkeypatch)
    _assert_well_formed(collect(), name)


@pytest.mark.parametrize(
    "exc",
    [RuntimeError("boom"), PermissionError("denied"), ImportError("gone"), ZeroDivisionError()],
)
def test_d3_run_collector_never_propagates(exc: Exception) -> None:
    def collect(problems: Problems) -> int:
        raise exc

    section = run_collector("probe", collect)
    assert section.data is None
    assert not section.available
    assert section.problems[0].source == "probe"
