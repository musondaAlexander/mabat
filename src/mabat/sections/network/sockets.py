"""Socket-level connections (``netstat`` style) via psutil, with owning process names."""

from __future__ import annotations

from collections import Counter
from typing import Any

from mabat._shared.models import ProblemKind, Problems
from mabat.sections.network.models import Connection, ConnectionsReport

_PROTOCOLS = {"SOCK_STREAM": "tcp", "SOCK_DGRAM": "udp"}
_FAMILIES = {"AF_INET": "ipv4", "AF_INET6": "ipv6"}


def _name(raw: Any) -> str:
    return str(getattr(raw, "name", raw))


def _process_names(psutil: Any, pids: set[int]) -> dict[int, str | None]:
    gone = getattr(psutil, "NoSuchProcess", ProcessLookupError)
    denied = getattr(psutil, "AccessDenied", PermissionError)
    names: dict[int, str | None] = {}
    for pid in pids:
        try:
            names[pid] = str(psutil.Process(pid).name())
        except (gone, denied):
            names[pid] = None
    return names


def read_connections(
    psutil: Any, problems: Problems, kind: str = "inet"
) -> ConnectionsReport | None:
    denied = getattr(psutil, "AccessDenied", PermissionError)
    try:
        raw = list(psutil.net_connections(kind=kind))
    except denied as exc:
        problems.add(
            "psutil.net_connections",
            ProblemKind.PERMISSION_DENIED,
            f"listing sockets needs elevation on this platform ({exc})",
        )
        return None

    names = _process_names(psutil, {int(c.pid) for c in raw if c.pid})
    connections = []
    for conn in raw:
        local = conn.laddr
        remote = conn.raddr
        connections.append(
            Connection(
                family=_FAMILIES.get(_name(conn.family), _name(conn.family).lower()),
                protocol=_PROTOCOLS.get(_name(conn.type), _name(conn.type).lower()),
                local_address=str(local[0]) if local else "",
                local_port=int(local[1]) if local else 0,
                remote_address=str(remote[0]) if remote else None,
                remote_port=int(remote[1]) if remote else None,
                status=str(conn.status),
                pid=int(conn.pid) if conn.pid else None,
                process=names.get(int(conn.pid)) if conn.pid else None,
            )
        )
    connections.sort(
        key=lambda c: (c.status != "ESTABLISHED", c.status, c.process or "", c.local_port)
    )
    by_status = Counter(c.status for c in connections)
    return ConnectionsReport(
        connections=tuple(connections),
        by_status=dict(by_status),
        listening=by_status.get("LISTEN", 0),
        established=by_status.get("ESTABLISHED", 0),
    )
