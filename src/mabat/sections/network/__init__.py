"""Network section: interfaces, addresses, counters, throughput, connections."""

from mabat.sections.network.collector import connections, network
from mabat.sections.network.models import (
    Address,
    Connection,
    ConnectionsReport,
    Counters,
    Interface,
    NetworkReport,
    Rates,
)

__all__ = [
    "Address",
    "Connection",
    "ConnectionsReport",
    "Counters",
    "Interface",
    "NetworkReport",
    "Rates",
    "connections",
    "network",
]
