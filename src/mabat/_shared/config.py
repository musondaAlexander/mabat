"""Settings loaded from data (``defaults.toml``) with optional user overrides.

Resolution order, later wins: built-in defaults -> ``./mabat.toml`` -> ``$MABAT_CONFIG``
-> an explicit path given to :func:`load_settings`. This module is the only place mabat
reads environment variables (a guard test enforces it).
"""

from __future__ import annotations

import functools
import ipaddress
import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

ENV_CONFIG_PATH = "MABAT_CONFIG"
LOCAL_CONFIG_NAME = "mabat.toml"


class SettingsError(ValueError):
    """A settings file is malformed or contains an unknown key."""


@dataclass(frozen=True, slots=True)
class Thresholds:
    warn_percent: float
    critical_percent: float
    temperature_warn_c: float
    temperature_critical_c: float


@dataclass(frozen=True, slots=True)
class Settings:
    cpu_sample_seconds: float
    top_processes: int
    process_sample_seconds: float
    hidden_process_names: frozenset[str]
    thresholds: Thresholds
    hidden_interface_patterns: tuple[str, ...]
    probe_address: str


# (table, key) -> accepted types: the whole vocabulary a settings file may use
_SCHEMA: dict[tuple[str, str], tuple[type, ...]] = {
    ("sampling", "cpu_sample_seconds"): (int, float),
    ("processes", "top_n"): (int,),
    ("processes", "sample_seconds"): (int, float),
    ("processes", "hidden_names"): (list,),
    ("thresholds", "warn_percent"): (int, float),
    ("thresholds", "critical_percent"): (int, float),
    ("thresholds", "temperature_warn_c"): (int, float),
    ("thresholds", "temperature_critical_c"): (int, float),
    ("network", "hidden_interface_patterns"): (list,),
    ("network", "probe_address"): (str,),
}


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise SettingsError(f"{path}: invalid TOML: {exc}") from exc


def _validate(raw: Mapping[str, Any], origin: str) -> None:
    for table, entries in raw.items():
        if not isinstance(entries, Mapping):
            raise SettingsError(f"{origin}: [{table}] must be a table")
        for key, value in entries.items():
            expected = _SCHEMA.get((table, key))
            if expected is None:
                raise SettingsError(f"{origin}: unknown setting [{table}] {key}")
            if isinstance(value, bool) or not isinstance(value, expected):
                raise SettingsError(f"{origin}: [{table}] {key} has the wrong type")


def _merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = {table: dict(entries) for table, entries in base.items()}
    for table, entries in override.items():
        merged.setdefault(table, {}).update(entries)
    return merged


def _build(raw: Mapping[str, Any]) -> Settings:
    thresholds = Thresholds(
        warn_percent=float(raw["thresholds"]["warn_percent"]),
        critical_percent=float(raw["thresholds"]["critical_percent"]),
        temperature_warn_c=float(raw["thresholds"]["temperature_warn_c"]),
        temperature_critical_c=float(raw["thresholds"]["temperature_critical_c"]),
    )
    if thresholds.warn_percent > thresholds.critical_percent:
        raise SettingsError("[thresholds] warn_percent must not exceed critical_percent")
    if thresholds.temperature_warn_c > thresholds.temperature_critical_c:
        raise SettingsError(
            "[thresholds] temperature_warn_c must not exceed temperature_critical_c"
        )
    top_n = int(raw["processes"]["top_n"])
    if top_n < 0:
        raise SettingsError("[processes] top_n must not be negative")
    sample = float(raw["sampling"]["cpu_sample_seconds"])
    if sample < 0:
        raise SettingsError("[sampling] cpu_sample_seconds must not be negative")
    process_sample = float(raw["processes"]["sample_seconds"])
    if process_sample < 0:
        raise SettingsError("[processes] sample_seconds must not be negative")
    probe = str(raw["network"]["probe_address"]).strip()
    try:
        ipaddress.ip_address(probe)  # an IP literal: a hostname would trigger a DNS lookup
    except ValueError:
        raise SettingsError("[network] probe_address must be an IPv4 or IPv6 address") from None
    return Settings(
        cpu_sample_seconds=sample,
        top_processes=top_n,
        process_sample_seconds=process_sample,
        hidden_process_names=frozenset(str(n) for n in raw["processes"]["hidden_names"]),
        thresholds=thresholds,
        hidden_interface_patterns=tuple(
            str(pattern) for pattern in raw["network"]["hidden_interface_patterns"]
        ),
        probe_address=probe,
    )


def _override_paths(explicit: Path | None) -> list[Path]:
    candidates = [Path.cwd() / LOCAL_CONFIG_NAME]
    from_env = os.environ.get(ENV_CONFIG_PATH)
    if from_env:
        candidates.append(Path(from_env))
    if explicit is not None:
        candidates.append(explicit)
    return candidates


def load_settings(path: str | os.PathLike[str] | None = None) -> Settings:
    """Load settings from the built-in defaults plus any override files present."""
    defaults_text = resources.files("mabat._shared").joinpath("defaults.toml").read_text("utf-8")
    raw = tomllib.loads(defaults_text)
    _validate(raw, "defaults.toml")

    explicit = Path(path) if path is not None else None
    for candidate in _override_paths(explicit):
        if candidate == explicit and not candidate.is_file():
            raise SettingsError(f"settings file not found: {candidate}")
        if candidate.is_file():
            override = _read_toml(candidate)
            _validate(override, str(candidate))
            raw = _merge(raw, override)
    return _build(raw)


@functools.cache
def settings() -> Settings:
    """Process-wide settings, loaded once. Call ``settings.cache_clear()`` to reload."""
    return load_settings()
