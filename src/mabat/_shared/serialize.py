"""The single outward serialisation path.

Every consumer - CLI ``--json``, a FastAPI response, a Streamlit dataframe - goes through
:func:`to_dict` / :func:`to_json`. Internal objects (psutil namedtuples, NVML handles,
WMI rows) are rejected so they can never leak across the boundary by accident.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import PurePath
from typing import Any

type Json = bool | int | float | str | list[Json] | dict[str, Json] | None


def to_dict(obj: object) -> Json:
    """Convert a mabat model into JSON-compatible builtins.

    Raises ``TypeError`` for anything that is not a mabat dataclass, a container of them,
    or a JSON primitive - by design, so foreign objects fail loudly.
    """
    if obj is None or isinstance(obj, bool | int | str):
        return obj
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, datetime | date):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return to_dict(obj.value)
    if isinstance(obj, PurePath):
        return str(obj)
    if is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_dict(getattr(obj, f.name)) for f in fields(obj)}
    if isinstance(obj, tuple) and hasattr(obj, "_fields"):
        raise TypeError(
            f"{type(obj).__name__} is a namedtuple; convert it to a mabat model before serialising"
        )
    if isinstance(obj, list | tuple | set | frozenset):
        return [to_dict(item) for item in obj]
    if isinstance(obj, Mapping):
        return {str(key): to_dict(value) for key, value in obj.items()}
    raise TypeError(f"{type(obj).__qualname__} is not serialisable by mabat")


def to_json(obj: object, *, indent: int | None = None) -> str:
    """Serialise a mabat model to a JSON string (always valid JSON: no NaN/Infinity)."""
    return json.dumps(to_dict(obj), indent=indent, ensure_ascii=False, allow_nan=False)


def flatten(obj: object, *, prefix: str = "", separator: str = ".") -> dict[str, Any]:
    """Flatten a model into ``{"cpu.usage.percent": 12.5, ...}`` - handy for dataframes."""
    out: dict[str, Any] = {}

    def walk(value: Json, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                walk(child, f"{path}{separator}{key}" if path else key)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}{separator}{index}" if path else str(index))
        else:
            out[path] = value

    walk(to_dict(obj), prefix)
    return out
