"""Network models: interfaces with addresses, link state, counters and rates; optional
socket-level connections."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Address:
    """``family`` is ``ipv4``, ``ipv6`` or ``mac``."""

    family: str
    address: str
    netmask: str | None
    broadcast: str | None


@dataclass(frozen=True, slots=True)
class Counters:
    """Cumulative since boot."""

    bytes_sent: int
    bytes_recv: int
    packets_sent: int
    packets_recv: int
    errors_in: int
    errors_out: int
    drops_in: int
    drops_out: int


@dataclass(frozen=True, slots=True)
class Rates:
    """Throughput since the previous ``network()`` call in this process."""

    sent_bytes_per_s: float
    recv_bytes_per_s: float
    interval_seconds: float


@dataclass(frozen=True, slots=True)
class Interface:
    """``hidden`` marks interfaces matching ``[network] hidden_interface_patterns``; they
    stay in the data and are merely collapsed by the CLI. ``speed_mbps`` is ``None`` when
    the driver reports 0 (unknown)."""

    name: str
    is_up: bool | None
    speed_mbps: int | None
    mtu: int | None
    duplex: str | None
    hidden: bool
    addresses: tuple[Address, ...]
    counters: Counters | None
    rates: Rates | None


@dataclass(frozen=True, slots=True)
class Connection:
    """One socket, ``netstat`` style. ``process`` is the owning process name when it
    could be resolved; command lines are never collected."""

    family: str
    protocol: str
    local_address: str
    local_port: int
    remote_address: str | None
    remote_port: int | None
    status: str
    pid: int | None
    process: str | None


@dataclass(frozen=True, slots=True)
class ConnectionsReport:
    connections: tuple[Connection, ...]
    by_status: dict[str, int]
    listening: int
    established: int


@dataclass(frozen=True, slots=True)
class NetworkReport:
    """``connections`` is ``None`` unless explicitly requested: it is large, noisy and on
    some platforms needs elevation."""

    hostname: str
    outbound_ip: str | None
    interfaces: tuple[Interface, ...]
    totals: Counters | None
    total_rates: Rates | None
    connections: ConnectionsReport | None
