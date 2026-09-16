"""Privacy guard: things that must never appear in any serialised payload (AGENT.md §1.3).

P1  Environment variable *values* never reach a payload (a canary is planted and hunted).
P2  Forbidden keys never appear anywhere in a payload: environments, process command lines
    (they carry tokens and passwords), and anything named like a credential.

Hostnames, usernames, IPs and MAC addresses are deliberately *allowed*: they are what an
observation tool reports. Masking them is a redaction feature (see BACKLOG.md), not a guard.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest

import mabat
from mabat._shared.serialize import to_json

CANARY_NAME = "MABAT_GUARD_CANARY"
CANARY_VALUE = "canary-7f3a9c-do-not-leak"

FORBIDDEN_KEYS = {
    "env",
    "environ",
    "environment",
    "cmdline",
    "command_line",
    "commandline",
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "credential",
    "credentials",
}


def _payloads() -> Iterator[tuple[str, str]]:
    yield "health", to_json(mabat.health())
    snap = mabat.snapshot()
    yield "snapshot", to_json(snap)
    for name, section in mabat.sections_of(snap).items():
        yield name, to_json(section)


def _keys(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from _keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _keys(child)


def test_p1_environment_values_never_leak(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(CANARY_NAME, CANARY_VALUE)
    leaks = [name for name, text in _payloads() if CANARY_VALUE in text or CANARY_NAME in text]
    assert not leaks, f"environment canary found in payload(s): {leaks}"


def test_p2_no_forbidden_keys_in_any_payload() -> None:
    offenders = []
    for name, text in _payloads():
        for key in _keys(json.loads(text)):
            if key.lower() in FORBIDDEN_KEYS:
                offenders.append(f"{name}: {key}")
    assert not offenders, "forbidden keys in payload(s): " + ", ".join(offenders)


def test_privacy_guard_covers_every_section() -> None:
    """If a section is registered it must be scanned; the guard must not pass vacuously."""
    scanned = {name for name, _ in _payloads()}
    assert set(mabat.section_names()) <= scanned
    assert {"health", "snapshot"} <= scanned
