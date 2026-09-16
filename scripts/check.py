"""Run every quality gate the Definition of Done requires, in order, and stop at the first
failure. Cross-platform; used locally and by CI so the two can never drift.

    python scripts/check.py            # all gates
    python scripts/check.py --fix      # let ruff format and auto-fix first
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

GATES: tuple[tuple[str, list[str]], ...] = (
    ("format", ["ruff", "format", "--check", "."]),
    ("lint", ["ruff", "check", "."]),
    ("types", ["mypy"]),
    ("tests", ["pytest"]),
)

FIXERS: tuple[list[str], ...] = (
    ["ruff", "format", "."],
    ["ruff", "check", "--fix", "."],
)


def run(label: str, args: list[str]) -> bool:
    print(f"\n=== {label}: {' '.join(args)}", flush=True)
    return subprocess.run(args, cwd=ROOT, check=False).returncode == 0


def main(argv: list[str]) -> int:
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
