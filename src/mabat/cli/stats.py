"""One headline number per target, and min/avg/max of it over a watch session."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from mabat._snapshot import Snapshot

Headline = tuple[str, float]  # (label, value)


def _cpu(report: Any) -> Headline | None:
    return ("cpu %", report.usage.percent) if report.usage else None


def _memory(report: Any) -> Headline | None:
    return ("RAM %", report.virtual.percent) if report.virtual else None


def _system(report: Any) -> Headline | None:
    if report.processes and report.processes.top:
        return ("top process %", report.processes.top[0].cpu_percent)
    return None


def _storage(report: Any) -> Headline | None:
    used = [p.percent for p in (report.partitions or ()) if p.percent is not None]
    return ("fullest volume %", max(used)) if used else None


def _gpu(report: Any) -> Headline | None:
    for device in report.devices:
        t = device.telemetry
        if t and t.utilization_percent is not None:
            return ("gpu %", t.utilization_percent)
    return None


def _sensors(report: Any) -> Headline | None:
    if report.temperatures:
        return ("hottest C", max(t.celsius for t in report.temperatures))
    return None


def _network(report: Any) -> Headline | None:
    if report.total_rates:
        return ("down KiB/s", report.total_rates.recv_bytes_per_s / 1024)
    return None


HEADLINES: dict[str, Callable[[Any], Headline | None]] = {
    "cpu": _cpu,
    "memory": _memory,
    "system": _system,
    "storage": _storage,
    "gpu": _gpu,
    "sensors": _sensors,
    "network": _network,
}


def headline(result: Any) -> Headline | None:
    """The one number worth tracking for a section (or a snapshot's CPU figure)."""
    if isinstance(result, Snapshot):
        section: Any = result.cpu
    else:
        section = result
    if section.data is None:
        return None
    pick = HEADLINES.get(section.name)
    return pick(section.data) if pick else None


@dataclass(slots=True)
class SessionStats:
    """Running min / mean / max over the frames seen so far."""

    label: str | None = None
    count: int = 0
    minimum: float = field(default=float("inf"))
    maximum: float = field(default=float("-inf"))
    total: float = 0.0

    def add(self, value: Headline | None) -> None:
        if value is None:
            return
        self.label, number = value
        self.count += 1
        self.minimum = min(self.minimum, number)
        self.maximum = max(self.maximum, number)
        self.total += number

    @property
    def mean(self) -> float:
        return self.total / self.count if self.count else 0.0

    def summary(self, separator: str = " | ") -> str | None:
        if not self.count or self.label is None:
            return None
        return separator.join(
            [
                f"{self.label}: min {self.minimum:.1f}",
                f"avg {self.mean:.1f}",
                f"max {self.maximum:.1f}",
                f"{self.count} frame{'s' if self.count != 1 else ''}",
            ]
        )
