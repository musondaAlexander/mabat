"""Sensor models: temperatures, fans and power draw, each tagged with the hardware that
reports it (a CPU package, a GPU, a drive, a motherboard chip)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Temperature:
    """``high_c``/``critical_c`` are the sensor's own limits when it publishes them."""

    hardware: str
    label: str
    celsius: float
    high_c: float | None
    critical_c: float | None


@dataclass(frozen=True, slots=True)
class Fan:
    hardware: str
    label: str
    rpm: float


@dataclass(frozen=True, slots=True)
class Power:
    hardware: str
    label: str
    watts: float


@dataclass(frozen=True, slots=True)
class SensorsReport:
    """``provider`` names the backend the readings came from: ``psutil`` (Linux hwmon)
    or ``librehardwaremonitor`` / ``openhardwaremonitor`` (their WMI namespaces)."""

    provider: str
    temperatures: tuple[Temperature, ...]
    fans: tuple[Fan, ...]
    powers: tuple[Power, ...]
