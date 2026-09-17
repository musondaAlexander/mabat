"""Run every quality gate the Definition of Done requires, in order, and stop at the first
failure. Cross-platform; used locally, by CI and by the git hooks so the three can never
drift.

    python scripts/check.py                  # all gates
    python scripts/check.py --fix            # let ruff format and auto-fix first
    python scripts/check.py --quick [FILES]  # format + lint (autofix) only; the commit hook

Whoever invokes this (a GUI's git, a bare shell) may not have the project venv on PATH.
If the current interpreter lacks the project or its tools, the script re-runs itself with
the repository's own venv interpreter; every tool is then run as ``python -m`` so nothing
leaks in from another environment.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIRED_MODULES = ("mabat", "ruff", "mypy", "pytest")
VENV_INTERPRETERS = (
    ROOT / "venv" / "Scripts" / "python.exe",
    ROOT / "venv" / "bin" / "python",
    ROOT / ".venv" / "Scripts" / "python.exe",
    ROOT / ".venv" / "bin" / "python",
)

PY = [sys.executable, "-m"]
GATES: tuple[tuple[str, list[str]], ...] = (
    ("format", [*PY, "ruff", "format", "--check", "."]),
    ("lint", [*PY, "ruff", "check", "."]),
    ("types", [*PY, "mypy"]),
    ("tests", [*PY, "pytest"]),
)
FIXERS: tuple[list[str], ...] = (
    [*PY, "ruff", "format", "."],
    [*PY, "ruff", "check", "--fix", "."],
)


def _has_project_tools() -> bool:
    return all(importlib.util.find_spec(name) is not None for name in REQUIRED_MODULES)


def _reexec_in_venv(argv: list[str]) -> int | None:
    """Re-run under the repository venv when this interpreter is not it. ``None`` = no need."""
    if _has_project_tools():
        return None
    here = Path(sys.executable).resolve()
    for candidate in VENV_INTERPRETERS:
        if candidate.exists() and candidate.resolve() != here:
            return subprocess.run(
                [str(candidate), str(Path(__file__)), *argv], check=False
            ).returncode
    missing = [name for name in REQUIRED_MODULES if importlib.util.find_spec(name) is None]
    print(
        f"{sys.executable} lacks {', '.join(missing)} and no project venv was found under "
        f'{ROOT}. Activate the venv or run: pip install -e ".[all,dev]"',
        file=sys.stderr,
    )
    return 1


def run(label: str, args: list[str]) -> bool:
    print(f"\n=== {label}: {' '.join(args[2:] if args[:2] == PY else args)}", flush=True)
    return subprocess.run(args, cwd=ROOT, check=False).returncode == 0


def main(argv: list[str]) -> int:
    code = _reexec_in_venv(argv)
    if code is not None:
        return code
    if "--quick" in argv:
        files = [arg for arg in argv if arg != "--quick"] or ["."]
        ok = run("format", [*PY, "ruff", "format", *files])
        ok = run("lint", [*PY, "ruff", "check", "--fix", *files]) and ok
        return 0 if ok else 1
    if "--fix" in argv:
        for fixer in FIXERS:
            run("fix", fixer)
    for label, args in GATES:
        if not run(label, args):
            print(f"\nFAILED at gate: {label}", file=sys.stderr)
            return 1
    print("\nall gates green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
