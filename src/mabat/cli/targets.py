"""What a command collects and how it draws it.

A ``Target`` is a section name or ``"snapshot"`` plus the collector options the user gave.
Flags map onto collector options through :data:`FLAGS`; which sections accept which
option comes from the ``Snapshot`` field metadata (``mabat.snapshot_options()``), so the
CLI never hard-codes "``--top`` is for system".
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

import typer
from rich.console import RenderableType

import mabat
from mabat.cli.render import error_console, render_section
from mabat.cli.render.network import render_network
from mabat.cli.render.snapshot import render_snapshot

SNAPSHOT = "snapshot"

# CLI flag -> the collector option(s) it sets. One flag may feed several sections
# (--sample is the CPU window and the per-process window).
FLAGS: dict[str, tuple[str, ...]] = {
    "--sample": ("sample_seconds", "process_sample_seconds"),
    "--top": ("top_n",),
    "--all-partitions": ("all_partitions",),
    "--no-smart": ("smart",),
    "--connections": ("connections",),
}


def targets() -> tuple[str, ...]:
    return (*mabat.section_names(), SNAPSHOT)


def collector_options(
    *,
    sample: float | None = None,
    top: int | None = None,
    all_partitions: bool = False,
    no_smart: bool = False,
    connections: bool = False,
) -> dict[str, Any]:
    """Collector options from CLI flag values; flags left at their default are absent."""
    options: dict[str, Any] = {}
    if sample is not None:
        options["sample_seconds"] = sample
        options["process_sample_seconds"] = sample
    if top is not None:
        options["top_n"] = top
    if all_partitions:
        options["all_partitions"] = True
    if no_smart:
        options["smart"] = False
    if connections:
        options["connections"] = True
    return options


def _flag_for(option: str) -> str:
    return next(flag for flag, names in FLAGS.items() if option in names)


class Target:
    def __init__(
        self,
        name: str,
        *,
        options: dict[str, Any] | None = None,
        only: list[str] | None = None,
        skip: list[str] | None = None,
        show_hidden: bool = False,
    ) -> None:
        self.name = name
        options = dict(options or {})
        accepted = mabat.snapshot_options()
        if name == SNAPSHOT:
            self._collect: Callable[[], Any] = lambda: mabat.snapshot(only, skip, **options)
            self._render: Callable[[Any], RenderableType] = render_snapshot
            return

        collect = mabat.collectors().get(name)
        if collect is None:
            error_console.print(
                f"[red]unknown section {name!r}[/red] - choose from: {', '.join(targets())}"
            )
            raise typer.Exit(code=2)
        mine = {opt: value for opt, value in options.items() if name in accepted.get(opt, ())}
        # a flag is misapplied only if none of the options it sets reach this section
        for option in options:
            flag = _flag_for(option)
            if not any(name in accepted.get(o, ()) for o in FLAGS[flag]):
                applies_to = sorted({s for o in FLAGS[flag] for s in accepted.get(o, ())})
                error_console.print(
                    f"[red]{flag} does not apply to {name!r}[/red] - it applies to: "
                    + ", ".join(applies_to)
                )
                raise typer.Exit(code=2)
        self._collect = functools.partial(collect, **mine)
        if name == "network" and show_hidden:
            self._render = functools.partial(render_network, show_hidden=True)
        else:
            self._render = render_section

    def collect(self) -> Any:
        try:
            return self._collect()
        except ValueError as exc:  # unknown --only/--skip names, negative windows
            error_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=2) from None

    def render(self, result: Any) -> RenderableType:
        return self._render(result)

    @staticmethod
    def available(result: Any) -> bool:
        if isinstance(result, mabat.Snapshot):
            return any(s.available for s in mabat.sections_of(result).values())
        return bool(result.available)
