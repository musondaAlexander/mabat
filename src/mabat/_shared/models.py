"""The one result shape every collector returns.

A :class:`Section` either carries ``data`` (possibly alongside partial ``problems``) or
carries ``data=None`` and a ``problems`` tuple explaining why. Collectors never raise to
their callers; :func:`run_collector` is what enforces that contract.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

log = logging.getLogger("mabat")


class ProblemKind(StrEnum):
    """Why a reading (or part of one) could not be taken."""

    MISSING_DEPENDENCY = "missing_dependency"
    UNSUPPORTED_PLATFORM = "unsupported_platform"
    PERMISSION_DENIED = "permission_denied"
    NOT_PRESENT = "not_present"
    BACKEND_ERROR = "backend_error"


@dataclass(frozen=True, slots=True)
class Problem:
    """A single, human-readable reason a reading is missing or partial."""

    source: str
    kind: ProblemKind
    detail: str

    @classmethod
    def from_exception(cls, source: str, exc: BaseException) -> Problem:
        message = str(exc).strip()
        detail = f"{type(exc).__name__}: {message}" if message else type(exc).__name__
        return cls(source=source, kind=classify_exception(exc), detail=detail)


def classify_exception(exc: BaseException) -> ProblemKind:
    """Map an exception to a :class:`ProblemKind`.

    Exceptions may carry their own ``kind`` attribute (see ``_shared.platform``); otherwise
    the standard library's hierarchy gives us a good enough signal.
    """
    explicit = getattr(exc, "kind", None)
    if isinstance(explicit, ProblemKind):
        return explicit
    if isinstance(exc, ImportError):
        return ProblemKind.MISSING_DEPENDENCY
    if isinstance(exc, PermissionError):
        return ProblemKind.PERMISSION_DENIED
    if isinstance(exc, NotImplementedError):
        return ProblemKind.UNSUPPORTED_PLATFORM
    return ProblemKind.BACKEND_ERROR


class Problems:
    """Mutable sink a collector records partial failures into while it works."""

    def __init__(self) -> None:
        self._items: list[Problem] = []

    def add(self, source: str, kind: ProblemKind, detail: str) -> None:
        self._items.append(Problem(source=source, kind=kind, detail=detail))

    def capture(self, source: str, exc: BaseException) -> None:
        problem = Problem.from_exception(source, exc)
        log.debug("%s: %s", source, problem.detail)
        self._items.append(problem)

    def freeze(self) -> tuple[Problem, ...]:
        return tuple(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __bool__(self) -> bool:
        return bool(self._items)


@dataclass(frozen=True, slots=True)
class Section[T]:
    """One domain's reading: ``data`` when available, ``problems`` explaining any gaps."""

    name: str
    collected_at: datetime
    data: T | None
    problems: tuple[Problem, ...] = ()
    available: bool = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "available", self.data is not None)


def now() -> datetime:
    """Timezone-aware UTC timestamp; the single clock every collector stamps with."""
    return datetime.now(UTC)


def run_collector[T](name: str, collect: Callable[[Problems], T]) -> Section[T]:
    """Run ``collect`` and wrap the outcome in a :class:`Section`, never raising.

    ``collect`` receives a :class:`Problems` sink for partial failures. Any exception it
    lets escape becomes a whole-section problem with ``data=None``.
    """
    problems = Problems()
    data: T | None
    try:
        data = collect(problems)
    except Exception as exc:  # broad on purpose: failures become data, never exceptions
        log.warning("collector %r failed: %s", name, exc, exc_info=log.isEnabledFor(logging.DEBUG))
        problems.capture(name, exc)
        data = None
    section: Section[T] = Section(
        name=name, collected_at=now(), data=data, problems=problems.freeze()
    )
    log.debug("collected %r available=%s problems=%d", name, section.available, len(problems))
    return section
