"""Speedtest section: an opt-in bandwidth test against speedtest.net.

Never part of ``snapshot()``: it moves tens of megabytes and takes ~30 s. Requires the
``speedtest-cli`` package (``mabat[speedtest]``).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from mabat._shared import platform as plat
from mabat._shared.models import ProblemKind, Problems, Section, run_collector

SECTION = "speedtest"
INSTALL_HINT = "pip install speedtest-cli (or: pip install 'mabat[speedtest]')"


@dataclass(frozen=True, slots=True)
class SpeedtestServer:
    name: str
    sponsor: str | None
    country: str | None
    host: str | None
    distance_km: float | None
    latency_ms: float | None


@dataclass(frozen=True, slots=True)
class SpeedtestReport:
    """Bits per second, like the speedtest.net UI. ``public_ip`` is the address the test
    server saw; ``--redact`` masks it."""

    download_bps: float
    upload_bps: float
    ping_ms: float
    server: SpeedtestServer | None
    public_ip: str | None
    isp: str | None
    duration_seconds: float


def _float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _server(raw: Any) -> SpeedtestServer | None:
    if not isinstance(raw, dict) or not raw:
        return None
    return SpeedtestServer(
        name=str(raw.get("name") or raw.get("host") or "unknown"),
        sponsor=raw.get("sponsor") or None,
        country=raw.get("country") or None,
        host=raw.get("host") or None,
        distance_km=_float(raw.get("d")),
        latency_ms=_float(raw.get("latency")),
    )


def read_speedtest(module: Any, problems: Problems) -> SpeedtestReport | None:
    started = time.perf_counter()
    try:
        test = module.Speedtest(secure=True)
        test.get_best_server()
        test.download()
        test.upload()
    except Exception as exc:  # the library raises its own hierarchy; all mean "no result"
        kind = ProblemKind.BACKEND_ERROR
        problems.add(
            SECTION, kind, f"{type(exc).__name__}: {exc} (offline, or speedtest.net unreachable?)"
        )
        return None
    results = test.results
    client = getattr(results, "client", None) or {}
    return SpeedtestReport(
        download_bps=float(results.download),
        upload_bps=float(results.upload),
        ping_ms=float(results.ping),
        server=_server(getattr(results, "server", None)),
        public_ip=client.get("ip") or None if isinstance(client, dict) else None,
        isp=client.get("isp") or None if isinstance(client, dict) else None,
        duration_seconds=round(time.perf_counter() - started, 1),
    )


def speedtest() -> Section[SpeedtestReport]:
    """Run a bandwidth test. Sends and receives real traffic; takes about half a minute."""

    def collect(problems: Problems) -> SpeedtestReport | None:
        module = plat.optional_import("speedtest")
        if module is None:
            problems.add(SECTION, ProblemKind.MISSING_DEPENDENCY, INSTALL_HINT)
            return None
        return read_speedtest(module, problems)

    return run_collector(SECTION, collect)


__all__ = ["SpeedtestReport", "SpeedtestServer", "read_speedtest", "speedtest"]
