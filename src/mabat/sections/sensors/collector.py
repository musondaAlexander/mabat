"""Pick the sensor provider this platform can actually answer with."""

from __future__ import annotations

from mabat._shared import platform as plat
from mabat._shared.models import ProblemKind, Problems, Section, run_collector
from mabat.sections.sensors.models import SensorsReport
from mabat.sections.sensors.providers import read_hardware_monitor, read_psutil

SECTION = "sensors"


def sensors() -> Section[SensorsReport]:
    """Temperatures, fans and power draw.

    Linux reads hwmon through psutil. Windows needs LibreHardwareMonitor running; the
    section says so (``missing_dependency``) until it is. macOS is unsupported.
    """

    def collect(problems: Problems) -> SensorsReport | None:
        psutil = plat.optional_import("psutil")
        if psutil is not None and hasattr(psutil, "sensors_temperatures"):
            return read_psutil(psutil, problems)
        if plat.IS_WINDOWS:
            return read_hardware_monitor(problems)
        problems.add(
            SECTION,
            ProblemKind.UNSUPPORTED_PLATFORM,
            "no temperature or fan API on this platform"
            + (" (macOS: third-party SMC readers only)" if plat.IS_MACOS else ""),
        )
        return None

    return run_collector(SECTION, collect)
