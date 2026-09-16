"""Compose interfaces, totals, outbound IP and (on request) connections."""

from __future__ import annotations

import platform as _platform

from mabat._shared import platform as plat
from mabat._shared.config import settings
from mabat._shared.models import ProblemKind, Problems, Section, attempt, run_collector
from mabat.sections.network.interfaces import outbound_ip, read_interfaces, read_totals
from mabat.sections.network.models import ConnectionsReport, NetworkReport
from mabat.sections.network.sockets import read_connections

SECTION = "network"
CONNECTIONS_SECTION = "connections"


def network(*, connections: bool = False) -> Section[NetworkReport]:
    """Interfaces, addresses, link state, counters and throughput since the last call.

    ``connections=True`` also lists sockets (large; needs elevation on macOS).
    """
    conf = settings()

    def collect(problems: Problems) -> NetworkReport | None:
        psutil = plat.optional_import("psutil")
        if psutil is None:
            problems.add("psutil", ProblemKind.MISSING_DEPENDENCY, "psutil is not installed")
            return None
        interfaces = read_interfaces(psutil, problems, conf.hidden_interface_patterns)
        totals, total_rates = read_totals(psutil, problems)
        sockets = None
        if connections:
            sockets = attempt(problems, "connections", lambda: read_connections(psutil, problems))
        if interfaces is None and totals is None and sockets is None:
            return None
        return NetworkReport(
            hostname=_platform.node(),
            outbound_ip=outbound_ip(conf.probe_address, problems),
            interfaces=interfaces or (),
            totals=totals,
            total_rates=total_rates,
            connections=sockets,
        )

    return run_collector(SECTION, collect)


def connections(kind: str = "inet") -> Section[ConnectionsReport]:
    """Just the socket table, ``netstat`` style. Not part of ``snapshot()``."""

    def collect(problems: Problems) -> ConnectionsReport | None:
        psutil = plat.optional_import("psutil")
        if psutil is None:
            problems.add("psutil", ProblemKind.MISSING_DEPENDENCY, "psutil is not installed")
            return None
        return read_connections(psutil, problems, kind)

    return run_collector(CONNECTIONS_SECTION, collect)
