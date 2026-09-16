"""Expose mabat over HTTP with FastAPI.

    pip install fastapi uvicorn
    uvicorn examples.fastapi_app:app --reload
    curl http://127.0.0.1:8000/snapshot?skip=sensors

Every endpoint returns ``mabat.to_dict(...)`` - the same JSON ``mabat ... --json`` prints -
so the CLI and the API can never disagree. Collectors are synchronous (the CPU section
blocks for its sample window); FastAPI runs ``def`` endpoints in a thread pool, so the
event loop stays free.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException

import mabat

app = FastAPI(title="mabat", version=mabat.__version__)


def _split(value: str | None) -> list[str] | None:
    return [part.strip() for part in value.split(",") if part.strip()] if value else None


@app.get("/health")
def health() -> Any:
    """Which data sources work on this host; use it as the service health check too."""
    return mabat.to_dict(mabat.health())


@app.get("/snapshot")
def snapshot(only: str | None = None, skip: str | None = None, connections: bool = False) -> Any:
    """Everything at once. ``?only=cpu,memory`` / ``?skip=sensors`` trim the work."""
    try:
        snap = mabat.snapshot(only=_split(only), skip=_split(skip), connections=connections)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return mabat.to_dict(snap)


@app.get("/sections/{name}")
def section(name: str) -> Any:
    """One section: ``/sections/cpu``. 404 for unknown names, never a 500 for missing hardware."""
    collect = mabat.collectors().get(name)
    if collect is None:
        raise HTTPException(status_code=404, detail=f"unknown section {name!r}")
    return mabat.to_dict(collect())


@app.get("/connections")
def connections() -> Any:
    """Open sockets with owning process names (large; opt-in for a reason)."""
    return mabat.to_dict(mabat.connections())


@app.get("/problems")
def problems() -> Any:
    """A flat list of everything this host cannot report, for a status page."""
    snap = mabat.snapshot(skip=["system"])  # the process scan is the slow part
    return [
        {"section": name, **mabat.to_dict(problem)}  # type: ignore[dict-item]
        for name, problem in mabat.problems_of(snap)
    ]
