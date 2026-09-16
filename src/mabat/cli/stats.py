"""One headline number per target, and min/avg/max of it over a session.

Headlines are read from the *JSON payload* (``to_dict`` output) rather than the models,
so a live ``watch`` frame and a line replayed from a ``--log`` file go through the same
code.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

Headline = tuple[str, float]  # (label, value)
Payload = Mapping[str, Any]


def _get(payload: Any, *path: str | int) -> Any:
    for step in path:
        if isinstance(step, int):
            if not isinstance(payload, list) or len(payload) <= step:
                return None
            payload = payload[step]
        else:
            if not isinstance(payload, Mapping):
                return None
            payload = payload.get(step)
        if payload is None:
            return None
    return payload


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def _cpu(data: Payload) -> Headline | None:
    value = _number(_get(data, "usage", "percent"))
    return ("cpu %", value) if value is not None else None


def _memory(data: Payload) -> Headline | None:
    value = _number(_get(data, "virtual", "percent"))
    return ("RAM %", value) if value is not None else None


def _system(data: Payload) -> Headline | None:
    value = _number(_get(data, "processes", "top", 0, "cpu_percent"))
    return ("top process %", value) if value is not None else None


def _storage(data: Payload) -> Headline | None:
    used = [
        p
        for p in (_number(_get(part, "percent")) for part in _get(data, "partitions") or [])
        if p is not None
    ]
    return ("fullest volume %", max(used)) if used else None


def _gpu(data: Payload) -> Headline | None:
    for device in _get(data, "devices") or []:
        value = _number(_get(device, "telemetry", "utilization_percent"))
        if value is not None:
            return ("gpu %", value)
    return None


def _sensors(data: Payload) -> Headline | None:
    temps = [
        t
        for t in (_number(_get(item, "celsius")) for item in _get(data, "temperatures") or [])
        if t is not None
    ]
    return ("hottest C", max(temps)) if temps else None


def _network(data: Payload) -> Headline | None:
    value = _number(_get(data, "total_rates", "recv_bytes_per_s"))
    return ("down KiB/s", value / 1024) if value is not None else None


HEADLINES: dict[str, Callable[[Payload], Headline | None]] = {
    "cpu": _cpu,
    "memory": _memory,
    "system": _system,
    "storage": _storage,
    "gpu": _gpu,
    "sensors": _sensors,
    "network": _network,
}


def headline(payload: Payload) -> Headline | None:
    """The one number worth tracking for a section payload (or a snapshot's CPU figure)."""
    section: Any = payload.get("cpu") if "hostname" in payload and "cpu" in payload else payload
    if not isinstance(section, Mapping) or section.get("data") is None:
        return None
    pick = HEADLINES.get(str(section.get("name")))
    return pick(section["data"]) if pick else None


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
