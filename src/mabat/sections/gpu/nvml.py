"""NVIDIA telemetry through NVML (``nvidia-ml-py``), the library behind ``nvidia-smi``.

Every reading is individually guarded: boards differ in what they expose, and one
unsupported query (fan speed on most laptops) must not blank the rest. Unsupported
readings are reported together as a single ``not_present`` problem.
"""

from __future__ import annotations

import contextlib
import dataclasses
from collections.abc import Callable
from typing import Any

from mabat._shared import platform as plat
from mabat._shared.models import ProblemKind, Problems
from mabat.sections.gpu.models import GpuClocks, GpuDevice, GpuMemory, GpuTelemetry

SOURCE = "nvml"
INSTALL_HINT = "pip install nvidia-ml-py (needs an NVIDIA GPU and driver)"


def _text(value: object) -> str | None:
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return str(value) if value is not None else None


class _Reader:
    """Calls NVML getters for one handle, remembering which ones the board rejects."""

    def __init__(self, nv: Any, handle: Any) -> None:
        self.nv = nv
        self.handle = handle
        self.unsupported: list[str] = []
        self.errors: list[str] = []

    def get[T](self, label: str, read: Callable[[], T]) -> T | None:
        try:
            return read()
        except self.nv.NVMLError as exc:
            if getattr(exc, "value", None) == getattr(self.nv, "NVML_ERROR_NOT_SUPPORTED", -1):
                self.unsupported.append(label)
            else:
                self.errors.append(f"{label}: {exc}")
            return None

    def memory(self) -> GpuMemory | None:
        info = self.get("memory", lambda: self.nv.nvmlDeviceGetMemoryInfo(self.handle))
        if info is None:
            return None
        total = int(info.total)
        return GpuMemory(
            total_bytes=total,
            used_bytes=int(info.used),
            free_bytes=int(info.free),
            percent=round(100.0 * int(info.used) / total, 1) if total else 0.0,
        )

    def clocks(self) -> GpuClocks | None:
        nv, h = self.nv, self.handle
        graphics = self.get(
            "clock_graphics", lambda: nv.nvmlDeviceGetClockInfo(h, nv.NVML_CLOCK_GRAPHICS)
        )
        memory = self.get("clock_memory", lambda: nv.nvmlDeviceGetClockInfo(h, nv.NVML_CLOCK_MEM))
        maximum = self.get(
            "clock_graphics_max", lambda: nv.nvmlDeviceGetMaxClockInfo(h, nv.NVML_CLOCK_GRAPHICS)
        )
        if graphics is None and memory is None and maximum is None:
            return None
        return GpuClocks(graphics_mhz=graphics, memory_mhz=memory, graphics_max_mhz=maximum)

    def telemetry(self) -> GpuTelemetry:
        nv, h = self.nv, self.handle
        util = self.get("utilization", lambda: nv.nvmlDeviceGetUtilizationRates(h))
        encoder = self.get("encoder", lambda: nv.nvmlDeviceGetEncoderUtilization(h))
        decoder = self.get("decoder", lambda: nv.nvmlDeviceGetDecoderUtilization(h))
        power = self.get("power", lambda: nv.nvmlDeviceGetPowerUsage(h))
        limit = self.get("power_limit", lambda: nv.nvmlDeviceGetEnforcedPowerLimit(h))
        graphics_procs = self.get(
            "processes", lambda: len(nv.nvmlDeviceGetGraphicsRunningProcesses(h))
        )
        compute_procs = self.get(
            "processes", lambda: len(nv.nvmlDeviceGetComputeRunningProcesses(h))
        )
        processes = None
        if graphics_procs is not None or compute_procs is not None:
            processes = (graphics_procs or 0) + (compute_procs or 0)
        return GpuTelemetry(
            memory=self.memory(),
            utilization_percent=float(util.gpu) if util is not None else None,
            memory_controller_percent=float(util.memory) if util is not None else None,
            encoder_percent=float(encoder[0]) if encoder else None,
            decoder_percent=float(decoder[0]) if decoder else None,
            temperature_c=self.get(
                "temperature", lambda: int(nv.nvmlDeviceGetTemperature(h, nv.NVML_TEMPERATURE_GPU))
            ),
            temperature_slowdown_c=self.get(
                "temperature_slowdown",
                lambda: int(
                    nv.nvmlDeviceGetTemperatureThreshold(h, nv.NVML_TEMPERATURE_THRESHOLD_SLOWDOWN)
                ),
            ),
            power_watts=round(power / 1000.0, 1) if power is not None else None,
            power_limit_watts=round(limit / 1000.0, 1) if limit is not None else None,
            fan_percent=self.get("fan", lambda: int(nv.nvmlDeviceGetFanSpeed(h))),
            clocks=self.clocks(),
            performance_state=self.get(
                "performance_state", lambda: int(nv.nvmlDeviceGetPerformanceState(h))
            ),
            pcie_generation=self.get(
                "pcie_generation", lambda: int(nv.nvmlDeviceGetCurrPcieLinkGeneration(h))
            ),
            pcie_width=self.get("pcie_width", lambda: int(nv.nvmlDeviceGetCurrPcieLinkWidth(h))),
            processes=processes,
        )

    def device(self) -> GpuDevice:
        nv, h = self.nv, self.handle
        telemetry = self.telemetry()
        pci = self.get("pci", lambda: nv.nvmlDeviceGetPciInfo(h))
        return GpuDevice(
            name=_text(self.get("name", lambda: nv.nvmlDeviceGetName(h))) or "NVIDIA GPU",
            vendor="NVIDIA",
            sources=(SOURCE,),
            physical=True,
            driver_version=None,  # filled in by the caller: it is system-wide
            memory_total_bytes=telemetry.memory.total_bytes if telemetry.memory else None,
            bus_id=_text(getattr(pci, "busId", None)) if pci is not None else None,
            uuid=_text(self.get("uuid", lambda: nv.nvmlDeviceGetUUID(h))),
            vbios=_text(self.get("vbios", lambda: nv.nvmlDeviceGetVbiosVersion(h))),
            processor=None,
            display=None,
            telemetry=telemetry,
        )


def read_nvml(problems: Problems) -> tuple[tuple[GpuDevice, ...], str | None] | None:
    """(devices, driver version), or ``None`` with a problem when NVML is unusable."""
    nv = plat.optional_import("pynvml")
    if nv is None:
        problems.add(SOURCE, ProblemKind.MISSING_DEPENDENCY, INSTALL_HINT)
        return None
    try:
        nv.nvmlInit()
    except nv.NVMLError as exc:
        problems.add(SOURCE, ProblemKind.NOT_PRESENT, f"NVML could not start: {exc}")
        return None
    try:
        driver = _text(nv.nvmlSystemGetDriverVersion())
        count = int(nv.nvmlDeviceGetCount())
        devices: list[GpuDevice] = []
        unsupported: set[str] = set()
        for index in range(count):
            reader = _Reader(nv, nv.nvmlDeviceGetHandleByIndex(index))
            device = reader.device()
            devices.append(dataclasses.replace(device, driver_version=driver))
            unsupported.update(reader.unsupported)
            for error in reader.errors:
                problems.add(SOURCE, ProblemKind.BACKEND_ERROR, f"GPU {index}: {error}")
        if unsupported:
            problems.add(
                SOURCE,
                ProblemKind.NOT_PRESENT,
                "not reported by this board: " + ", ".join(sorted(unsupported)),
            )
        return tuple(devices), driver
    finally:
        with contextlib.suppress(nv.NVMLError):
            nv.nvmlShutdown()
