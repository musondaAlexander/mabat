"""Interfaces, addresses, link state, counters and inter-call throughput via psutil."""

from __future__ import annotations

import socket
import time
from collections.abc import Iterable
from fnmatch import fnmatch
from typing import Any

from mabat._shared.models import Problems, attempt
from mabat.sections.network.models import Address, Counters, Interface, Rates

_FAMILY_NAMES = {"AF_INET": "ipv4", "AF_INET6": "ipv6", "AF_LINK": "mac", "AF_PACKET": "mac"}
_DUPLEX_NAMES = {2: "full", 1: "half", 0: None}

# Previous counters per interface ("" = system total), for throughput between calls.
_previous: dict[str, tuple[float, int, int]] = {}


def reset_rates() -> None:
    """Forget previous counters (tests)."""
    _previous.clear()


def _family(raw: Any) -> str:
    name = getattr(raw, "name", str(raw))
    return _FAMILY_NAMES.get(name, name.lower())


def _addresses(entries: Iterable[Any]) -> tuple[Address, ...]:
    return tuple(
        Address(
            family=_family(entry.family),
            address=str(entry.address).split("%", 1)[0],  # drop IPv6 scope ids
            netmask=entry.netmask or None,
            broadcast=entry.broadcast or None,
        )
        for entry in entries
    )


def _counters(raw: Any) -> Counters:
    return Counters(
        bytes_sent=int(raw.bytes_sent),
        bytes_recv=int(raw.bytes_recv),
        packets_sent=int(raw.packets_sent),
        packets_recv=int(raw.packets_recv),
        errors_in=int(raw.errin),
        errors_out=int(raw.errout),
        drops_in=int(raw.dropin),
        drops_out=int(raw.dropout),
    )


def _rates(key: str, counters: Counters, now: float) -> Rates | None:
    previous = _previous.get(key)
    _previous[key] = (now, counters.bytes_sent, counters.bytes_recv)
    if previous is None:
        return None
    then, sent, recv = previous
    interval = now - then
    if interval <= 0 or counters.bytes_sent < sent or counters.bytes_recv < recv:
        return None  # clock went backwards or counters reset
    return Rates(
        sent_bytes_per_s=(counters.bytes_sent - sent) / interval,
        recv_bytes_per_s=(counters.bytes_recv - recv) / interval,
        interval_seconds=interval,
    )


def read_interfaces(
    psutil: Any, problems: Problems, hidden_patterns: Iterable[str]
) -> tuple[Interface, ...] | None:
    addrs = attempt(problems, "psutil.net_if_addrs", psutil.net_if_addrs)
    if addrs is None:
        return None
    stats = attempt(problems, "psutil.net_if_stats", psutil.net_if_stats) or {}
    io = (
        attempt(problems, "psutil.net_io_counters", lambda: psutil.net_io_counters(pernic=True))
        or {}
    )
    patterns = tuple(hidden_patterns)
    now = time.monotonic()

    interfaces = []
    for name in sorted(set(addrs) | set(stats) | set(io)):
        stat = stats.get(name)
        counters = _counters(io[name]) if name in io else None
        speed = int(stat.speed) if stat is not None and stat.speed else None
        interfaces.append(
            Interface(
                name=str(name),
                is_up=bool(stat.isup) if stat is not None else None,
                speed_mbps=speed,
                mtu=int(stat.mtu) if stat is not None and stat.mtu else None,
                duplex=_DUPLEX_NAMES.get(int(stat.duplex)) if stat is not None else None,
                hidden=any(fnmatch(str(name), pattern) for pattern in patterns),
                addresses=_addresses(addrs.get(name, ())),
                counters=counters,
                rates=_rates(str(name), counters, now) if counters else None,
            )
        )
    return tuple(interfaces)


def read_totals(psutil: Any, problems: Problems) -> tuple[Counters | None, Rates | None]:
    raw = attempt(problems, "psutil.net_io_counters", lambda: psutil.net_io_counters(pernic=False))
    if raw is None:
        return None, None
    counters = _counters(raw)
    return counters, _rates("", counters, time.monotonic())


def outbound_ip(probe_address: str, problems: Problems) -> str | None:
    """The local address the default route uses. A UDP ``connect`` sends nothing."""

    def probe() -> str:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(1.0)
            sock.connect((probe_address, 80))
            return str(sock.getsockname()[0])

    return attempt(problems, "socket.outbound", probe)
