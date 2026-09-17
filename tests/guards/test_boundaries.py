"""Boundary guard: mabat's architecture rules as executable checks (AGENT.md §4.3, §9).

R1  Only ``mabat/cli/`` may import UI libraries (typer, rich, click).
R2  Outside ``mabat/cli/`` the package statically imports only the standard library and
    itself (backends arrive through ``optional_import``); under ``cli/`` only the ``cli`` extra.
R3  A section never imports another section.
R4  Sections import ``mabat._shared`` only - never the composers, the CLI or top-level mabat.
R5  ``mabat/_shared/`` never imports upward (sections, composers, CLI, top-level mabat).
R6  ``subprocess`` and shell-outs exist only in ``mabat/_shared/platform.py``.
R7  Environment variables are read only in ``mabat/_shared/config.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

from tests.guards.conftest import SRC, attribute_uses, imports_of, module_name, source_files

UI_LIBRARIES = {"typer", "rich", "click"}
CLI_EXTRA = UI_LIBRARIES | {"prompt_toolkit"}  # the ``cli`` extra in pyproject.toml
SHELL_MODULES = {"subprocess", "pty", "commands"}
SHELL_ATTRIBUTES = {"os.system", "os.popen", "os.execv", "os.execvp", "os.spawnv", "os.startfile"}
ENV_ATTRIBUTES = {"os.environ", "os.getenv", "os.putenv", "os.environb"}

SUBPROCESS_SITE = SRC / "_shared" / "platform.py"
ENVIRONMENT_SITE = SRC / "_shared" / "config.py"


def _top(name: str) -> str:
    return name.split(".", 1)[0]


def _section_of(path: Path) -> str | None:
    parts = path.relative_to(SRC).parts
    return parts[1] if len(parts) >= 3 and parts[0] == "sections" else None


def _is_under(path: Path, *segments: str) -> bool:
    return path.relative_to(SRC).parts[: len(segments)] == segments


def _fail(rule: str, violations: list[str]) -> None:
    assert not violations, f"{rule} violated:\n  " + "\n  ".join(violations)


def test_r1_ui_libraries_only_in_cli() -> None:
    violations = [
        f"{path.relative_to(SRC)}:{line} imports {name}"
        for path in source_files()
        if not _is_under(path, "cli")
        for name, line in imports_of(path)
        if _top(name) in UI_LIBRARIES
    ]
    _fail("R1 (typer/rich/click only under mabat/cli/)", violations)


def test_r2_only_declared_dependencies_are_imported() -> None:
    violations = []
    for path in source_files():
        allowed = CLI_EXTRA if _is_under(path, "cli") else set()
        violations += [
            f"{path.relative_to(SRC)}:{line} imports {name}"
            for name, line in imports_of(path)
            if _top(name) not in sys.stdlib_module_names
            and _top(name) != "mabat"
            and _top(name) not in allowed
        ]
    _fail("R2 (core imports stdlib + mabat only; cli/ adds the cli extra)", violations)


def test_r3_sections_never_import_each_other() -> None:
    violations = []
    for path in source_files():
        own = _section_of(path)
        if own is None:
            continue
        for name, line in imports_of(path):
            parts = name.split(".")
            if parts[:2] == ["mabat", "sections"] and len(parts) > 2 and parts[2] != own:
                violations.append(f"{path.relative_to(SRC)}:{line} imports {name}")
    _fail("R3 (sections are isolated from one another)", violations)


def test_r4_sections_depend_only_on_shared() -> None:
    allowed_prefixes = ("mabat._shared",)
    violations = []
    for path in source_files():
        own = _section_of(path)
        if own is None:
            continue
        for name, line in imports_of(path):
            if not name.startswith("mabat"):
                continue
            if name.startswith(allowed_prefixes) or name.startswith(f"mabat.sections.{own}"):
                continue
            violations.append(f"{path.relative_to(SRC)}:{line} imports {name}")
    _fail("R4 (sections import mabat._shared and themselves only)", violations)


def test_r5_shared_kernel_never_imports_upward() -> None:
    violations = [
        f"{path.relative_to(SRC)}:{line} imports {name}"
        for path in source_files()
        if _is_under(path, "_shared")
        for name, line in imports_of(path)
        if name == "mabat" or (name.startswith("mabat.") and not name.startswith("mabat._shared"))
    ]
    _fail("R5 (_shared has no upward dependencies)", violations)


def test_r6_subprocess_only_in_platform_helper() -> None:
    violations = []
    for path in source_files():
        if path == SUBPROCESS_SITE:
            continue
        violations += [
            f"{path.relative_to(SRC)}:{line} imports {name}"
            for name, line in imports_of(path)
            if _top(name) in SHELL_MODULES
        ]
        violations += [
            f"{path.relative_to(SRC)}:{line} calls {name}"
            for name, line in attribute_uses(path, SHELL_ATTRIBUTES)
        ]
    _fail("R6 (only _shared/platform.py may spawn processes)", violations)


def test_r7_environment_read_only_in_config() -> None:
    violations = []
    for path in source_files():
        if path == ENVIRONMENT_SITE:
            continue
        violations += [
            f"{path.relative_to(SRC)}:{line} uses {name}"
            for name, line in attribute_uses(path, ENV_ATTRIBUTES)
        ]
        violations += [
            f"{path.relative_to(SRC)}:{line} imports {name}"
            for name, line in imports_of(path)
            if name in {"os.environ", "os.getenv", "os.putenv"}
        ]
    _fail("R7 (only _shared/config.py may read the environment)", violations)


def test_guard_helpers_see_the_package() -> None:
    """The scanners must actually find mabat, or every rule above passes vacuously."""
    files = list(source_files())
    assert any(module_name(p) == "mabat" for p in files)
    assert any(module_name(p) == "mabat._shared.platform" for p in files)
    assert any(name == "subprocess" for name, _ in imports_of(SUBPROCESS_SITE))
