"""System models: OS identity, uptime, logged-in users, battery and a process summary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class OsIdentity:
    system: str
    release: str
    version: str
    platform: str
    machine: str
    hostname: str
    distribution: str | None
    python: str


@dataclass(frozen=True, slots=True)
class Uptime:
    boot_time: datetime
    uptime_seconds: float


@dataclass(frozen=True, slots=True)
class User:
    name: str
    terminal: str | None
    host: str | None
    started: datetime | None
    pid: int | None


@dataclass(frozen=True, slots=True)
class Battery:
    """``seconds_left`` is ``None`` when unknown or when running on mains power."""

    percent: float
    seconds_left: int | None
    power_plugged: bool | None


@dataclass(frozen=True, slots=True)
class ProcessInfo:
    """One process. Command lines and environments are deliberately never collected
    (privacy guard P2): they routinely carry tokens and passwords."""

    pid: int
    name: str
    username: str | None
    status: str
    cpu_percent: float
    memory_percent: float
    memory_rss_bytes: int
    threads: int | None
    created: datetime | None


@dataclass(frozen=True, slots=True)
class ProcessSummary:
    """``top`` holds the ``top_n`` busiest processes by CPU, then resident memory.
    ``cpu_percent`` is normalised to the whole machine (0-100) like Task Manager, not
    per-core like ``top``. ``total`` counts every visible process."""

    total: int
    top: tuple[ProcessInfo, ...]
    top_n: int
    sample_seconds: float
    inaccessible: int


@dataclass(frozen=True, slots=True)
class SystemReport:
    os: OsIdentity | None
    uptime: Uptime | None
    users: tuple[User, ...] | None
    battery: Battery | None
    processes: ProcessSummary | None
