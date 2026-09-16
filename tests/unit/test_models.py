from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC

import pytest

from mabat._shared.models import (
    Problem,
    ProblemKind,
    Problems,
    Section,
    classify_exception,
    now,
    run_collector,
)


def test_now_is_timezone_aware_utc() -> None:
    assert now().tzinfo is UTC


def test_section_available_tracks_data() -> None:
    assert Section(name="x", collected_at=now(), data=1).available is True
    assert Section(name="x", collected_at=now(), data=None).available is False


def test_section_is_immutable() -> None:
    section = Section(name="x", collected_at=now(), data=1)
    with pytest.raises(FrozenInstanceError):
        section.data = 2  # type: ignore[misc]


@pytest.mark.parametrize(
    ("exc", "kind"),
    [
        (ModuleNotFoundError("no module named nope"), ProblemKind.MISSING_DEPENDENCY),
        (PermissionError("denied"), ProblemKind.PERMISSION_DENIED),
        (NotImplementedError("mac"), ProblemKind.UNSUPPORTED_PLATFORM),
        (RuntimeError("boom"), ProblemKind.BACKEND_ERROR),
    ],
)
def test_classify_exception_by_hierarchy(exc: BaseException, kind: ProblemKind) -> None:
    assert classify_exception(exc) is kind


def test_classify_exception_honours_explicit_kind() -> None:
    class TaggedError(RuntimeError):
        kind = ProblemKind.NOT_PRESENT

    assert classify_exception(TaggedError()) is ProblemKind.NOT_PRESENT


def test_problem_from_exception_formats_detail() -> None:
    assert Problem.from_exception("gpu", RuntimeError("boom")).detail == "RuntimeError: boom"
    assert Problem.from_exception("gpu", RuntimeError()).detail == "RuntimeError"


def test_problems_sink_collects_and_freezes() -> None:
    sink = Problems()
    assert not sink
    sink.add("cpu", ProblemKind.NOT_PRESENT, "no cache info")
    sink.capture("cpu", ValueError("bad"))
    frozen = sink.freeze()
    assert len(sink) == 2
    assert isinstance(frozen, tuple)
    assert frozen[1].kind is ProblemKind.BACKEND_ERROR


def test_run_collector_success_with_partial_problems() -> None:
    def collect(problems: Problems) -> dict[str, int]:
        problems.add("cpu", ProblemKind.NOT_PRESENT, "l3 unknown")
        return {"cores": 6}

    section = run_collector("cpu", collect)
    assert section.available
    assert section.data == {"cores": 6}
    assert section.name == "cpu"
    assert [p.detail for p in section.problems] == ["l3 unknown"]


def test_run_collector_turns_exception_into_problem() -> None:
    def collect(problems: Problems) -> int:
        raise PermissionError("need admin")

    section = run_collector("smart", collect)
    assert not section.available
    assert section.data is None
    assert section.problems[0].kind is ProblemKind.PERMISSION_DENIED
    assert section.problems[0].source == "smart"


def test_run_collector_lets_keyboard_interrupt_through() -> None:
    def collect(problems: Problems) -> int:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        run_collector("x", collect)
