"""Shared console, number formatting and the problems footer every renderer uses."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.text import Text

from mabat._shared.config import settings
from mabat._shared.models import Section

console = Console()
error_console = Console(stderr=True)

# Legacy Windows consoles (cp1252 and friends) cannot encode block glyphs; use ASCII there.
_UNICODE = "utf" in (console.encoding or "").lower()
FILLED = "█" if _UNICODE else "#"
EMPTY = "░" if _UNICODE else "-"
DOT = " · " if _UNICODE else " | "
ELLIPSIS = "…" if _UNICODE else "..."

_BINARY_UNITS = ("B", "KiB", "MiB", "GiB", "TiB", "PiB")


def fmt_bytes(value: int | None, *, precision: int = 1) -> str:
    """1536 -> '1.5 KiB'. Binary units, labelled honestly."""
    if value is None:
        return "-"
    size = float(value)
    for unit in _BINARY_UNITS:
        if size < 1024 or unit == _BINARY_UNITS[-1]:
            return f"{size:.{0 if unit == 'B' else precision}f} {unit}"
        size /= 1024
    return f"{size:.{precision}f} {_BINARY_UNITS[-1]}"


def fmt_hz(value: int | float | None, *, mhz: bool = False) -> str:
    """Hz (or MHz when ``mhz``) -> '3.29 GHz'."""
    if value is None:
        return "-"
    hz = float(value) * (1_000_000 if mhz else 1)
    if hz >= 1e9:
        return f"{hz / 1e9:.2f} GHz"
    if hz >= 1e6:
        return f"{hz / 1e6:.0f} MHz"
    return f"{hz:.0f} Hz"


def fmt_seconds(value: float | None) -> str:
    """Cumulative seconds -> '1d 03h 04m'."""
    if value is None:
        return "-"
    total = int(value)
    days, rest = divmod(total, 86_400)
    hours, rest = divmod(rest, 3_600)
    minutes, seconds = divmod(rest, 60)
    if days:
        return f"{days}d {hours:02d}h {minutes:02d}m"
    if hours:
        return f"{hours}h {minutes:02d}m {seconds:02d}s"
    return f"{minutes}m {seconds:02d}s"


def fmt_int(value: int | None) -> str:
    return "-" if value is None else f"{value:,}"


def pct_text(percent: float | None) -> Text:
    """Utilisation coloured by the configured warn/critical thresholds."""
    if percent is None:
        return Text("-", style="dim")
    limits = settings().thresholds
    if percent >= limits.critical_percent:
        style = "bold red"
    elif percent >= limits.warn_percent:
        style = "yellow"
    else:
        style = "green"
    return Text(f"{percent:.1f} %", style=style)


def bar(percent: float | None, *, width: int = 20) -> Text:
    """A text bar for a 0-100 value, coloured like ``pct_text``."""
    if percent is None:
        return Text("-", style="dim")
    filled = round(max(0.0, min(100.0, percent)) / 100 * width)
    return Text(FILLED * filled + EMPTY * (width - filled), style=pct_text(percent).style)


def kv_table(title: str | None = None) -> Table:
    """Two-column key/value grid used by every detail view."""
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold cyan", no_wrap=True)
    table.add_column()
    if title:
        console.print(Text(title, style="bold"))
    return table


def render_problems(section: Section[object]) -> None:
    """Footer explaining what could not be read. Silent when there is nothing to say."""
    if not section.problems:
        return
    table = Table.grid(padding=(0, 1))
    table.add_column(style="yellow", no_wrap=True)
    table.add_column(style="dim", no_wrap=True)
    table.add_column()
    for problem in section.problems:
        # Text() so brackets in sources/details are never parsed as Rich markup
        table.add_row("!", Text(f"{problem.source} [{problem.kind.value}]"), Text(problem.detail))
    console.print(table)
