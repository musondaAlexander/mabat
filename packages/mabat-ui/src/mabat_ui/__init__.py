"""``mabat-ui`` console script: run the bundled Streamlit app."""

from __future__ import annotations

import sys
from importlib import metadata
from pathlib import Path

APP_PATH = Path(__file__).with_name("app.py")

try:
    __version__ = metadata.version("mabat-ui")
except metadata.PackageNotFoundError:  # running from a checkout without an install
    __version__ = "0+unknown"


def main(argv: list[str] | None = None) -> None:
    """Equivalent to ``streamlit run mabat_ui/app.py <argv>``."""
    from streamlit.web import cli

    sys.argv = ["streamlit", "run", str(APP_PATH), *(sys.argv[1:] if argv is None else argv)]
    sys.exit(cli.main())


__all__ = ["APP_PATH", "__version__", "main"]
