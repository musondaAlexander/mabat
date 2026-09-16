"""Storage models: partitions with usage, per-disk I/O counters and SMART health."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Partition:
    """Usage fields are ``None`` when the volume could not be queried (an empty card
    reader, an unmounted network share)."""

    device: str
    mountpoint: str
    fstype: str
    options: str
    total_bytes: int | None
    used_bytes: int | None
    free_bytes: int | None
    percent: float | None


@dataclass(frozen=True, slots=True)
class DiskIo:
    """Cumulative counters since boot. ``busy_seconds`` is Linux-only."""

    name: str
    read_count: int
    write_count: int
    read_bytes: int
    write_bytes: int
    read_seconds: float
    write_seconds: float
    busy_seconds: float | None


@dataclass(frozen=True, slots=True)
class SmartAttribute:
    id: int | None
    name: str
    value: int | None
    worst: int | None
    threshold: int | None
    raw: str


@dataclass(frozen=True, slots=True)
class SmartDevice:
    """``assessment`` is smartctl's overall verdict ('PASS' / 'FAIL' / 'WARN')."""

    name: str
    model: str | None
    serial: str | None
    firmware: str | None
    interface: str | None
    capacity_bytes: int | None
    assessment: str | None
    temperature_c: int | None
    attributes: tuple[SmartAttribute, ...]


@dataclass(frozen=True, slots=True)
class StorageReport:
    partitions: tuple[Partition, ...] | None
    io: tuple[DiskIo, ...] | None
    smart: tuple[SmartDevice, ...] | None
