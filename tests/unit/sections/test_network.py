from __future__ import annotations

import json
import time
from collections import namedtuple
from collections.abc import Iterator
from enum import Enum
from types import SimpleNamespace
from typing import Any

import pytest

import mabat
from mabat._shared import platform as plat
from mabat._shared.models import ProblemKind, Problems
from mabat.sections.network import interfaces, sockets


class Fam(Enum):
    AF_INET = 2
    AF_INET6 = 23
    AF_LINK = -1


class Kind(Enum):
    SOCK_STREAM = 1
    SOCK_DGRAM = 2


Addr = namedtuple("Addr", "family address netmask broadcast")
Stat = namedtuple("Stat", "isup duplex speed mtu")
Io = namedtuple("Io", "bytes_sent bytes_recv packets_sent packets_recv errin errout dropin dropout")
Sock = namedtuple("Sock", "family type laddr raddr status pid")
Endpoint = namedtuple("Endpoint", "ip port")


class GoneError(Exception):
    pass


class DeniedError(Exception):
    pass


def _io(pernic: bool) -> Any:
    if pernic:
        return {"eth0": Io(1000, 2000, 10, 20, 0, 0, 0, 0), "lo": Io(5, 5, 1, 1, 0, 0, 0, 0)}
    return Io(1005, 2005, 11, 21, 0, 0, 0, 0)


def _fake_psutil(**overrides: Any) -> SimpleNamespace:
    base: dict[str, Any] = {
        "NoSuchProcess": GoneError,
        "AccessDenied": DeniedError,
        "net_if_addrs": lambda: {
            "eth0": [
                Addr(Fam.AF_LINK, "00-11-22-33-44-55", None, None),
                Addr(Fam.AF_INET, "192.168.1.10", "255.255.255.0", "192.168.1.255"),
                Addr(Fam.AF_INET6, "fe80::1%eth0", None, None),
            ],
            "lo": [Addr(Fam.AF_INET, "127.0.0.1", "255.0.0.0", None)],
        },
        "net_if_stats": lambda: {"eth0": Stat(True, 2, 1000, 1500), "lo": Stat(True, 0, 0, 65536)},
        "net_io_counters": lambda pernic=False: _io(pernic),
        "net_connections": lambda kind="inet": [
            Sock(
                Fam.AF_INET,
                Kind.SOCK_STREAM,
                Endpoint("10.0.0.2", 50000),
                Endpoint("1.1.1.1", 443),
                "ESTABLISHED",
                42,
            ),
            Sock(Fam.AF_INET, Kind.SOCK_STREAM, Endpoint("0.0.0.0", 22), (), "LISTEN", 7),  # noqa: S104 - test data
            Sock(Fam.AF_INET6, Kind.SOCK_DGRAM, Endpoint("::", 5353), (), "NONE", None),
        ],
        "Process": lambda pid: SimpleNamespace(name=lambda: {42: "chrome.exe", 7: "sshd"}[pid]),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture(autouse=True)
def _fresh_rates() -> Iterator[None]:
    interfaces.reset_rates()
    yield
    interfaces.reset_rates()


# --- interfaces ------------------------------------------------------------------------


def test_interfaces_addresses_stats_and_hidden_flag() -> None:
    problems = Problems()
    result = interfaces.read_interfaces(_fake_psutil(), problems, ["lo"])
    assert result is not None and [i.name for i in result] == ["eth0", "lo"]
    eth0, lo = result
    assert (eth0.is_up, eth0.speed_mbps, eth0.mtu, eth0.duplex) == (True, 1000, 1500, "full")
    assert [a.family for a in eth0.addresses] == ["mac", "ipv4", "ipv6"]
    assert eth0.addresses[2].address == "fe80::1"  # scope id stripped
    assert eth0.addresses[1].broadcast == "192.168.1.255"
    assert eth0.counters is not None and eth0.counters.bytes_recv == 2000
    assert eth0.rates is None  # first call: nothing to compare with
    assert lo.hidden and not eth0.hidden
    assert lo.speed_mbps is None and lo.duplex is None  # 0 means unknown
    assert not problems


def test_rates_appear_on_the_second_call(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = iter([100.0, 100.0, 102.0, 102.0])
    monkeypatch.setattr(time, "monotonic", lambda: next(clock))
    first = _fake_psutil()
    interfaces.read_interfaces(first, Problems(), ())
    interfaces.read_totals(first, Problems())

    def faster(pernic: bool = False) -> Any:
        if pernic:
            return {"eth0": Io(5000, 4000, 10, 20, 0, 0, 0, 0), "lo": Io(5, 5, 1, 1, 0, 0, 0, 0)}
        return Io(3005, 4005, 11, 21, 0, 0, 0, 0)

    second = _fake_psutil(net_io_counters=faster)
    result = interfaces.read_interfaces(second, Problems(), ())
    assert result is not None and result[0].rates is not None
    assert (result[0].rates.sent_bytes_per_s, result[0].rates.recv_bytes_per_s) == (2000.0, 1000.0)
    assert result[0].rates.interval_seconds == 2.0
    totals, total_rates = interfaces.read_totals(second, Problems())
    assert totals is not None and total_rates is not None
    assert total_rates.sent_bytes_per_s == 1000.0


def test_rates_reset_when_counters_go_backwards(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = iter([10.0, 11.0])
    monkeypatch.setattr(time, "monotonic", lambda: next(clock))
    interfaces.read_totals(_fake_psutil(), Problems())
    rebooted = _fake_psutil(net_io_counters=lambda pernic=False: Io(1, 1, 1, 1, 0, 0, 0, 0))
    _, rates = interfaces.read_totals(rebooted, Problems())
    assert rates is None


def test_interfaces_unavailable_without_addrs() -> None:
    def broken() -> None:
        raise OSError("no netlink")

    problems = Problems()
    assert interfaces.read_interfaces(_fake_psutil(net_if_addrs=broken), problems, ()) is None
    assert problems.freeze()[0].source == "psutil.net_if_addrs"


def test_outbound_ip_failure_is_a_problem() -> None:
    problems = Problems()
    assert interfaces.outbound_ip("256.256.256.256", problems) is None  # invalid address
    assert problems.freeze()[0].source == "socket.outbound"


# --- connections ------------------------------------------------------------------------


def test_connections_are_mapped_sorted_and_named() -> None:
    problems = Problems()
    report = sockets.read_connections(_fake_psutil(), problems)
    assert report is not None
    assert (report.established, report.listening) == (1, 1)
    assert report.by_status == {"ESTABLISHED": 1, "LISTEN": 1, "NONE": 1}
    first = report.connections[0]
    assert first.status == "ESTABLISHED" and first.process == "chrome.exe"
    assert (first.family, first.protocol) == ("ipv4", "tcp")
    assert (first.remote_address, first.remote_port) == ("1.1.1.1", 443)
    listening = report.connections[1]
    assert listening.remote_address is None and listening.process == "sshd"
    udp = report.connections[2]
    assert (udp.family, udp.protocol, udp.pid, udp.process) == ("ipv6", "udp", None, None)
    assert not problems


def test_connections_denied_is_a_problem() -> None:
    def denied(kind: str = "inet") -> None:
        raise DeniedError("psutil.AccessDenied")

    problems = Problems()
    fake = _fake_psutil(net_connections=denied)
    assert sockets.read_connections(fake, problems) is None
    assert problems.freeze()[0].kind is ProblemKind.PERMISSION_DENIED


def test_connections_process_lookup_failures_leave_name_empty() -> None:
    def process(pid: int) -> SimpleNamespace:
        raise GoneError if pid == 42 else DeniedError

    report = sockets.read_connections(_fake_psutil(Process=process), Problems())
    assert report is not None and all(c.process is None for c in report.connections)


# --- entry points ---------------------------------------------------------------------------


def test_network_without_psutil(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plat, "optional_import", lambda name: None)
    assert not mabat.network().available
    assert not mabat.connections().available


def test_network_embeds_connections_only_on_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plat, "optional_import", lambda name: _fake_psutil())
    plain = mabat.network()
    assert plain.available and plain.data is not None and plain.data.connections is None
    with_sockets = mabat.network(connections=True)
    assert with_sockets.data is not None and with_sockets.data.connections is not None
    assert with_sockets.data.connections.established == 1


def test_network_on_this_machine_serialises() -> None:
    section = mabat.network()
    assert section.available
    payload = json.loads(mabat.to_json(section))
    assert payload["data"]["interfaces"]
    for interface in payload["data"]["interfaces"]:
        assert {"name", "is_up", "hidden", "addresses", "counters", "rates"} <= set(interface)
    assert "connections" in payload["data"] and payload["data"]["connections"] is None


def test_network_with_denied_sockets_stays_available(monkeypatch: pytest.MonkeyPatch) -> None:
    """macOS without root: net_connections is denied, the rest of the section still works."""

    def denied(kind: str = "inet") -> None:
        raise DeniedError("psutil.AccessDenied")

    monkeypatch.setattr(plat, "optional_import", lambda name: _fake_psutil(net_connections=denied))
    section = mabat.network(connections=True)
    assert section.available and section.data is not None
    assert section.data.connections is None
    assert section.data.interfaces  # interfaces, counters, outbound ip are unaffected
    assert any(
        p.source == "psutil.net_connections" and p.kind is ProblemKind.PERMISSION_DENIED
        for p in section.problems
    )
