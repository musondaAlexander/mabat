"""mabat over HTTP.

Every endpoint returns ``mabat.to_dict(...)`` - the same JSON ``mabat ... --json`` prints -
so the CLI and the API can never disagree. Collectors are synchronous (the CPU section
blocks for its sample window); FastAPI runs ``def`` endpoints in a thread pool, so the
event loop stays free.
"""

from __future__ import annotations

from importlib import metadata
from typing import Any

from fastapi import FastAPI, HTTPException, Query

import mabat

try:
    __version__ = metadata.version("mabat-api")
except metadata.PackageNotFoundError:  # running from a checkout without an install
    __version__ = "0+unknown"


def _split(value: str | None) -> list[str] | None:
    return [part.strip() for part in value.split(",") if part.strip()] if value else None


def _finish(result: Any, redact: bool) -> Any:
    return mabat.to_dict(mabat.redact(result) if redact else result)


def create_app() -> FastAPI:
    app = FastAPI(
        title="mabat",
        version=__version__,
        description="Your machine's CPU, GPU, memory, storage, network and OS as JSON.",
    )

    @app.get("/health")
    def health() -> Any:
        """Which data sources work on this host; doubles as the service health check."""
        return mabat.to_dict(mabat.health())

    @app.get("/sections")
    def sections() -> Any:
        """Section names and the options each accepts."""
        options = mabat.snapshot_options()
        return {
            "sections": list(mabat.section_names()),
            "options": {name: list(accepted) for name, accepted in options.items()},
        }

    @app.get("/sections/{name}")
    def section(
        name: str,
        redact: bool = False,
        sample: float | None = Query(default=None, ge=0),
        top: int | None = Query(default=None, ge=0),
        connections: bool = False,
        counters: bool = False,
        smart: bool = True,
    ) -> Any:
        """One section, e.g. ``/sections/cpu``. 404 for unknown names, never a 500 for
        missing hardware - that is a ``problems`` entry in a 200."""
        collect = mabat.collectors().get(name)
        if collect is None:
            raise HTTPException(status_code=404, detail=f"unknown section {name!r}")
        accepted = mabat.snapshot_options()
        wanted = {
            "sample_seconds": sample,
            "process_sample_seconds": sample,
            "top_n": top,
            "connections": connections or None,
            "counters": counters or None,
            "smart": None if smart else False,
        }
        options = {
            key: value
            for key, value in wanted.items()
            if value is not None and name in accepted.get(key, ())
        }
        return _finish(collect(**options), redact)

    @app.get("/snapshot")
    def snapshot(
        only: str | None = None,
        skip: str | None = None,
        redact: bool = False,
        sample: float | None = Query(default=None, ge=0),
        top: int | None = Query(default=None, ge=0),
        connections: bool = False,
        counters: bool = False,
        smart: bool = True,
    ) -> Any:
        """Everything at once. ``?only=cpu,memory`` / ``?skip=sensors`` trim the work."""
        options: dict[str, Any] = {}
        if sample is not None:
            options["sample_seconds"] = sample
            options["process_sample_seconds"] = sample
        if top is not None:
            options["top_n"] = top
        if connections:
            options["connections"] = True
        if counters:
            options["counters"] = True
        if not smart:
            options["smart"] = False
        try:
            snap = mabat.snapshot(only=_split(only), skip=_split(skip), **options)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        return _finish(snap, redact)

    @app.get("/connections")
    def connections(kind: str = "inet", redact: bool = False) -> Any:
        """Open sockets with owning process names (large; opt-in for a reason)."""
        return _finish(mabat.connections(kind=kind), redact)

    @app.get("/problems")
    def problems() -> Any:
        """A flat list of everything this host cannot report, for a status page."""
        snap = mabat.snapshot(top_n=0)  # count processes, skip the slow per-process scan
        return [
            {"section": name, **mabat.to_dict(problem)}  # type: ignore[dict-item]
            for name, problem in mabat.problems_of(snap)
        ]

    return app


app = create_app()

__all__ = ["__version__", "app", "create_app"]
