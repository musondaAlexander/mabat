"""One-screen overview of a whole snapshot: a status line per section."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from rich.console import RenderableType
from rich.table import Table
from rich.text import Text

from mabat._shared.models import ProblemKind, Section
from mabat._snapshot import Snapshot, sections_of
from mabat.cli.render.common import DOT, assemble, fmt_bytes, fmt_hz, fmt_seconds
from mabat.cli.render.network import fmt_rate
from mabat.sections.cpu import CpuReport
from mabat.sections.gpu import GpuReport
from mabat.sections.memory import MemoryReport
from mabat.sections.network import NetworkReport
from mabat.sections.sensors import SensorsReport
from mabat.sections.storage import StorageReport
from mabat.sections.system import SystemReport

_ADAPTERS_NAMED = 1


def _cpu(report: CpuReport) -> str:
    parts = []
    if report.identity and report.identity.brand:
        parts.append(report.identity.brand)
    if report.usage:
        parts.append(f"{report.usage.percent:.1f} %")
        if report.usage.frequency and report.usage.frequency.current_mhz:
            parts.append(fmt_hz(report.usage.frequency.current_mhz, mhz=True))
    return DOT.join(parts)


def _memory(report: MemoryReport) -> str:
    parts = []
    if report.virtual:
        vm = report.virtual
        parts.append(
            f"RAM {vm.percent:.1f} % ({fmt_bytes(vm.used_bytes)} of {fmt_bytes(vm.total_bytes)})"
        )
    if report.swap and report.swap.total_bytes:
        parts.append(f"swap {report.swap.percent:.1f} %")
    return DOT.join(parts)


def _system(report: SystemReport) -> str:
    parts = []
    if report.os:
        parts.append(f"{report.os.system} {report.os.release}")
    if report.uptime:
        parts.append(f"up {fmt_seconds(report.uptime.uptime_seconds)}")
    if report.processes:
        parts.append(f"{report.processes.total} processes")
        if report.processes.top:
            busiest = report.processes.top[0]
            parts.append(f"top {busiest.name} {busiest.cpu_percent:.1f} %")
    if report.battery and not report.battery.power_plugged:
        parts.append(f"battery {report.battery.percent:.0f} %")
    return DOT.join(parts)


def _storage(report: StorageReport) -> str:
    parts = [
        f"{part.mountpoint} {part.percent:.1f} %"
        for part in (report.partitions or ())
        if part.percent is not None
    ]
    if report.smart:
        verdicts = {dev.assessment or "?" for dev in report.smart}
        parts.append("SMART " + "/".join(sorted(verdicts)))
    return DOT.join(parts)


def _gpu(report: GpuReport) -> str:
    parts = []
    for device in report.devices[:_ADAPTERS_NAMED]:
        bits = [device.name]
        telemetry = device.telemetry
        if telemetry:
            if telemetry.utilization_percent is not None:
                bits.append(f"{telemetry.utilization_percent:.0f} %")
            if telemetry.temperature_c is not None:
                bits.append(f"{telemetry.temperature_c} C")
            if telemetry.memory:
                bits.append(f"VRAM {telemetry.memory.percent:.1f} %")
        parts.append(" ".join(bits))
    remaining = len(report.devices) - _ADAPTERS_NAMED
    if remaining > 0:
        parts.append(f"+{remaining} adapter{'s' if remaining != 1 else ''}")
    return DOT.join(parts)


def _sensors(report: SensorsReport) -> str:
    parts = []
    if report.temperatures:
        hottest = max(report.temperatures, key=lambda t: t.celsius)
        parts.append(f"hottest {hottest.label} {hottest.celsius:.0f} C")
        parts.append(f"{len(report.temperatures)} temperatures")
    if report.fans:
        parts.append(f"{len(report.fans)} fans")
    if report.powers:
        parts.append(f"{sum(p.watts for p in report.powers):.0f} W")
    return DOT.join(parts) or f"via {report.provider}"


def _network(report: NetworkReport) -> str:
    parts = []
    if report.outbound_ip:
        parts.append(report.outbound_ip)
    if report.total_rates:
        parts.append(f"up {fmt_rate(report.total_rates.sent_bytes_per_s)}")
        parts.append(f"down {fmt_rate(report.total_rates.recv_bytes_per_s)}")
    elif report.totals:
        parts.append(f"{fmt_bytes(report.totals.bytes_sent)} sent")
        parts.append(f"{fmt_bytes(report.totals.bytes_recv)} received")
    up = sum(1 for i in report.interfaces if i.is_up and not i.hidden)
    parts.append(f"{up} interface{'s' if up != 1 else ''} up")
    return DOT.join(parts)


SUMMARIES: dict[str, Callable[[Any], str]] = {
    "cpu": _cpu,
    "memory": _memory,
    "system": _system,
    "storage": _storage,
    "gpu": _gpu,
    "sensors": _sensors,
    "network": _network,
}


def _status(section: Section[Any]) -> Text:
    if section.available:
        return Text("partial", style="yellow") if section.problems else Text("ok", style="green")
    if any(p.kind is ProblemKind.SKIPPED for p in section.problems):
        return Text("skipped", style="dim")
    return Text("unavailable", style="red")


def _summary(section: Section[Any]) -> Text:
    if section.data is not None:
        summarise = SUMMARIES.get(section.name)
        text = summarise(section.data) if summarise else ""
        return Text(text or "-")
    reason = section.problems[0].detail if section.problems else "no data"
    return Text(reason.split(". ")[0], style="dim")


def render_snapshot(snap: Snapshot) -> RenderableType:
    header = Text.assemble(
        (snap.hostname, "bold"),
        (f"{DOT}{snap.platform}{DOT}", "dim"),
        (snap.collected_at.astimezone().strftime("%Y-%m-%d %H:%M:%S"), "dim"),
    )
    table = Table(show_edge=False, pad_edge=False, box=None, header_style="bold")
    table.add_column("section", style="bold cyan", no_wrap=True)
    table.add_column("status", no_wrap=True)
    table.add_column("summary", overflow="fold")
    for name, section in sections_of(snap).items():
        table.add_row(name, _status(section), _summary(section))

    notes = [
        Text(f"! {name}: {problem.detail}", style="dim")
        for name, section in sections_of(snap).items()
        if section.available and section.problems
        for problem in section.problems[:1]
    ]
    return assemble(header, Text(""), table, Text("") if notes else None, *notes)
