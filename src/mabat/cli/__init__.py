"""Console entry point. The CLI is a thin renderer over the library and the only part of
mabat allowed to import typer/rich (a guard test enforces it)."""

from __future__ import annotations

import sys


def main() -> None:
    try:
        from mabat.cli.app import app
    except ImportError as exc:
        sys.stderr.write(
            f"mabat's command line needs the 'cli' extra: pip install 'mabat[cli]' ({exc})\n"
        )
        raise SystemExit(2) from exc
    app()
