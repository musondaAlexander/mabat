"""Mask identifying values before a reading leaves the machine.

Works on the models themselves (frozen dataclasses), so both the JSON path and the
rendered tables see the same masked data. Which field names count as identifying is
data: ``[redaction] keys`` in ``defaults.toml``.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable, Mapping
from typing import Any

from mabat._shared.config import settings

MASK = "[redacted]"


def redact[T](obj: T, keys: Iterable[str] | None = None) -> T:
    """A copy of ``obj`` with every string field named in ``keys`` replaced by ``MASK``.

    Nested dataclasses, tuples, lists and dicts are walked; anything else is returned as
    is. ``keys`` defaults to the configured redaction keys.
    """
    names = frozenset(keys) if keys is not None else settings().redaction_keys
    return _walk(obj, names)  # type: ignore[no-any-return]


def _walk(value: Any, names: frozenset[str]) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        changes = {}
        for spec in dataclasses.fields(value):
            if not spec.init:
                continue
            current = getattr(value, spec.name)
            if spec.name in names and isinstance(current, str) and current:
                changes[spec.name] = MASK
            else:
                changes[spec.name] = _walk(current, names)
        return dataclasses.replace(value, **changes)
    if isinstance(value, tuple):
        return tuple(_walk(item, names) for item in value)
    if isinstance(value, list):
        return [_walk(item, names) for item in value]
    if isinstance(value, Mapping):
        return {
            key: (MASK if key in names and isinstance(item, str) and item else _walk(item, names))
            for key, item in value.items()
        }
    return value
