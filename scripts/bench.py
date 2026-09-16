"""Thin wrapper: ``python scripts/bench.py`` == ``mabat bench``. Kept for the runbook."""

from __future__ import annotations

import sys

from mabat.cli import main

if __name__ == "__main__":
    sys.argv = [sys.argv[0], "bench", *sys.argv[1:]]
    main()
