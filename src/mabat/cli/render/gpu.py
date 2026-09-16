"""Renderer for the GPU section."""

from __future__ import annotations

from rich.console import RenderableType
from rich.text import Text

from mabat._shared.models import Section
from mabat.cli.render.common import (
    DOT,
    assemble,
    bar,
    fmt_bytes,
    kv_table,
    pct_text,
    problems_footer,
    temp_text,
)
from mabat.sections.gpu import GpuDevice, GpuReport, GpuTelemetry


def _identity(device: GpuDevice) -> RenderableType:
    title = Text.assemble(
        (device.name, "bold"),
        ("" if device.physical else "  (virtual adapter)", "dim italic"),
    )
    table = kv_table()
    if device.vendor:
        table.add_row("vendor", Text(device.vendor))
    if device.driver_version:
        table.add_row("driver", Text(device.driver_version))
    if device.memory_total_bytes and device.telemetry is None:
        table.add_row("memory", fmt_bytes(device.memory_total_bytes))
    if device.processor:
        table.add_row("processor", Text(device.processor))
    if device.display:
        refresh = f" @ {device.display.refresh_hz} Hz" if device.display.refresh_hz else ""
        table.add_row("display", f"{device.display.width}x{device.display.height}{refresh}")
    if device.bus_id:
        table.add_row("bus", Text(device.bus_id))
    if device.vbios:
        table.add_row("vbios", Text(device.vbios))
    table.add_row("sources", ", ".join(device.sources))
    return assemble(title, table)


def _telemetry(t: GpuTelemetry) -> RenderableType:
    table = kv_table()
    if t.utilization_percent is not None:
        table.add_row(
            "utilisation",
            Text.assemble(bar(t.utilization_percent), "  ", pct_text(t.utilization_percent)),
        )
    if t.memory:
        table.add_row(
            "memory",
            Text.assemble(
                bar(t.memory.percent),
                "  ",
                pct_text(t.memory.percent),
                f"{DOT}{fmt_bytes(t.memory.used_bytes)} of {fmt_bytes(t.memory.total_bytes)}",
            ),
        )
    if t.memory_controller_percent is not None:
        table.add_row("memory bus", pct_text(t.memory_controller_percent))
    if t.encoder_percent is not None or t.decoder_percent is not None:
        table.add_row(
            "video",
            f"encode {t.encoder_percent:g} %{DOT}decode {t.decoder_percent:g} %"
            if t.encoder_percent is not None and t.decoder_percent is not None
            else "-",
        )
    if t.temperature_c is not None:
        limit = f"{DOT}slowdown at {t.temperature_slowdown_c} C" if t.temperature_slowdown_c else ""
        table.add_row(
            "temperature",
            Text.assemble(temp_text(t.temperature_c, t.temperature_slowdown_c), (limit, "dim")),
        )
    if t.power_watts is not None:
        limit = f" of {t.power_limit_watts:g} W" if t.power_limit_watts else ""
        table.add_row("power", f"{t.power_watts:g} W{limit}")
    if t.fan_percent is not None:
        table.add_row("fan", pct_text(t.fan_percent))
    if t.clocks:
        graphics = f"{t.clocks.graphics_mhz} MHz" if t.clocks.graphics_mhz is not None else "-"
        maximum = f" (max {t.clocks.graphics_max_mhz})" if t.clocks.graphics_max_mhz else ""
        memory = f"{DOT}memory {t.clocks.memory_mhz} MHz" if t.clocks.memory_mhz is not None else ""
        table.add_row("clocks", f"graphics {graphics}{maximum}{memory}")
    state = []
    if t.performance_state is not None:
        state.append(f"P{t.performance_state}")
    if t.pcie_generation is not None and t.pcie_width is not None:
        state.append(f"PCIe gen{t.pcie_generation} x{t.pcie_width}")
    if t.processes is not None:
        state.append(f"{t.processes} process{'es' if t.processes != 1 else ''}")
    if state:
        table.add_row("state", DOT.join(state))
    return table


def render_gpu(section: Section[GpuReport]) -> RenderableType:
    report = section.data
    if report is None:
        return assemble(Text("GPU: unavailable", style="bold red"), problems_footer(section))
    parts: list[RenderableType | None] = []
    for index, device in enumerate(report.devices):
        if index:
            parts.append(Text(""))
        parts.append(_identity(device))
        if device.telemetry:
            parts.append(_telemetry(device.telemetry))
    parts.append(problems_footer(section))
    return assemble(*parts)
