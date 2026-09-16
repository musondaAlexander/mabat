"""Compose every domain section into one :class:`Snapshot`.

Sections are declared as dataclass fields carrying their collector in ``metadata``, so
the field list is the single source of truth for what a snapshot contains and in which
order it is collected. Domain sprints add one field each.
"""

from __future__ import annotations

import platform as _platform
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, fields
from datetime import datetime
from typing import Any

from mabat._shared.models import Section, now
from mabat._shared.platform import PLATFORM_NAME
from mabat.sections.cpu import CpuReport, cpu

type Collector = Callable[[], Section[Any]]

COLLECTOR_KEY = "collector"


@dataclass(frozen=True, slots=True)
class Snapshot:
    collected_at: datetime
    hostname: str
    platform: str
    # Domain sections, in collection order. Each field's metadata names its collector.
    cpu: Section[CpuReport] = field(metadata={COLLECTOR_KEY: cpu})


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


def snapshot() -> Snapshot:
    """Collect every section and return them as one immutable snapshot."""
    sections = {name: collect() for name, collect in collectors().items()}
    return Snapshot(
        collected_at=now(),
        hostname=_platform.node(),
        platform=PLATFORM_NAME,
        **sections,
    )


def sections_of(snap: Snapshot) -> Mapping[str, Section[Any]]:
    """The domain sections of a snapshot, keyed by name."""
    return {name: getattr(snap, name) for name in collectors()}
