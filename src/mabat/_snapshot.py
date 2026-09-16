"""Compose every domain section into one :class:`Snapshot`.

Sections are declared as dataclass fields carrying their collector in ``metadata``, so
the field list is the single source of truth for what a snapshot contains, in which
order it is collected, and which options each collector accepts.
"""

from __future__ import annotations

import platform as _platform
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field, fields
from datetime import datetime
from typing import Any

from mabat._shared.models import Problem, ProblemKind, Section, now
from mabat._shared.platform import PLATFORM_NAME
from mabat.sections.cpu import CpuReport, cpu
from mabat.sections.gpu import GpuReport, gpu
from mabat.sections.memory import MemoryReport, memory
from mabat.sections.network import NetworkReport, network
from mabat.sections.sensors import SensorsReport, sensors
from mabat.sections.storage import StorageReport, storage
from mabat.sections.system import SystemReport, system

type Collector = Callable[..., Section[Any]]

COLLECTOR_KEY = "collector"
OPTIONS_KEY = "options"  # names of keyword options the collector accepts


@dataclass(frozen=True, slots=True)
class Snapshot:
    collected_at: datetime
    hostname: str
    platform: str
    # Domain sections, in collection order. Each field's metadata names its collector.
    cpu: Section[CpuReport] = field(metadata={COLLECTOR_KEY: cpu, OPTIONS_KEY: ("sample_seconds",)})
    memory: Section[MemoryReport] = field(metadata={COLLECTOR_KEY: memory})
    system: Section[SystemReport] = field(
        metadata={COLLECTOR_KEY: system, OPTIONS_KEY: ("top_n", "process_sample_seconds")}
    )
    storage: Section[StorageReport] = field(
        metadata={COLLECTOR_KEY: storage, OPTIONS_KEY: ("all_partitions", "smart")}
    )
    gpu: Section[GpuReport] = field(metadata={COLLECTOR_KEY: gpu})
    sensors: Section[SensorsReport] = field(metadata={COLLECTOR_KEY: sensors})
    network: Section[NetworkReport] = field(
        metadata={COLLECTOR_KEY: network, OPTIONS_KEY: ("connections",)}
    )


def collectors() -> Mapping[str, Collector]:
    """Section name -> collector, in collection order."""
    found: dict[str, Collector] = {}
    for spec in fields(Snapshot):
        collector = spec.metadata.get(COLLECTOR_KEY)
        if collector is not None:
            found[spec.name] = collector
    return found


def section_names() -> tuple[str, ...]:
    return tuple(collectors())


def snapshot_options() -> Mapping[str, tuple[str, ...]]:
    """Option name -> the sections that accept it (``{"connections": ("network",)}``)."""
    accepted: dict[str, list[str]] = {}
    for spec in fields(Snapshot):
        for option in spec.metadata.get(OPTIONS_KEY, ()):
            accepted.setdefault(option, []).append(spec.name)
    return {option: tuple(names) for option, names in accepted.items()}


def _selection(only: Iterable[str] | None, skip: Iterable[str] | None) -> set[str]:
    names = section_names()
    chosen = set(only) if only is not None else set(names)
    dropped = set(skip) if skip is not None else set()
    unknown = (chosen | dropped) - set(names)
    if unknown:
        raise ValueError(
            f"unknown section(s): {', '.join(sorted(unknown))}; choose from {', '.join(names)}"
        )
    return chosen - dropped


def _skipped(name: str) -> Section[Any]:
    return Section(
        name=name,
        collected_at=now(),
        data=None,
        problems=(Problem(name, ProblemKind.SKIPPED, "not collected: skipped by request"),),
    )


def snapshot(
    only: Iterable[str] | None = None,
    skip: Iterable[str] | None = None,
    **options: Any,
) -> Snapshot:
    """Collect every section (or just ``only`` minus ``skip``) into one immutable snapshot.

    Keyword options are routed to the collectors that declare them (see
    :func:`snapshot_options`): ``snapshot(connections=True, top_n=0, smart=False)`` reaches
    ``network()``, ``system()`` and ``storage()`` respectively. Skipped sections are present
    with ``available=False`` and a ``skipped`` problem, so the shape never changes.
    """
    accepted = snapshot_options()
    unknown = set(options) - set(accepted)
    if unknown:
        raise TypeError(f"unknown snapshot option(s): {', '.join(sorted(unknown))}")
    wanted = _selection(only, skip)
    sections: dict[str, Section[Any]] = {}
    for name, collect in collectors().items():
        if name not in wanted:
            sections[name] = _skipped(name)
            continue
        kwargs = {opt: value for opt, value in options.items() if name in accepted[opt]}
        sections[name] = collect(**kwargs)
    return Snapshot(
        collected_at=now(),
        hostname=_platform.node(),
        platform=PLATFORM_NAME,
        **sections,
    )


def sections_of(snap: Snapshot) -> Mapping[str, Section[Any]]:
    """The domain sections of a snapshot, keyed by name."""
    return {name: getattr(snap, name) for name in collectors()}


def problems_of(snap: Snapshot) -> tuple[tuple[str, Problem], ...]:
    """Every problem in the snapshot as ``(section name, problem)`` pairs."""
    return tuple(
        (name, problem)
        for name, section in sections_of(snap).items()
        for problem in section.problems
    )
