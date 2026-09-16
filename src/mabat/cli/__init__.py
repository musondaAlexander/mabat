"""Console entry point. The CLI is a thin renderer over the library and the only part of
mabat allowed to import typer/rich (a guard test enforces it)."""

from __future__ import annotations

import contextlib
import errno
import os
import sys


def main() -> None:
    try:
        from mabat.cli.app import app
    except ImportError as exc:
        sys.stderr.write(
            f"mabat's command line needs the 'cli' extra: pip install 'mabat[cli]' ({exc})\n"
        )
        raise SystemExit(2) from exc
    try:
        app()
    except OSError as exc:
        # The reader went away (`mabat connections | head`): leave quietly like any CLI.
        # Windows reports a closed pipe as EINVAL rather than EPIPE. Point stdout at the
        # null device so the interpreter's final flush does not complain a second time.
        if exc.errno not in (errno.EPIPE, errno.EINVAL):
            raise
        with contextlib.suppress(OSError):
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        raise SystemExit(0) from None
