"""mabat - observe your machine as plain Python data.

Every reading is a frozen dataclass wrapped in a :class:`Section`; serialise any of them
with :func:`to_json`. Domain entry points (``cpu()``, ``memory()``, ...) are added here
as their modules land.
"""

from __future__ import annotations

import logging

from mabat._health import Health, ProviderStatus, health, version
from mabat._shared.config import Settings, load_settings, settings
from mabat._shared.models import Problem, ProblemKind, Section
from mabat._shared.serialize import flatten, to_dict, to_json
from mabat._snapshot import Snapshot, collectors, section_names, sections_of, snapshot
from mabat.sections.cpu import CpuReport, cpu
from mabat.sections.gpu import GpuReport, gpu
from mabat.sections.memory import MemoryReport, memory
from mabat.sections.network import ConnectionsReport, NetworkReport, connections, network
from mabat.sections.sensors import SensorsReport, sensors
from mabat.sections.storage import StorageReport, storage
from mabat.sections.system import SystemReport, system

__version__ = version()

__all__ = [
    "ConnectionsReport",
    "CpuReport",
    "GpuReport",
    "Health",
    "MemoryReport",
    "NetworkReport",
    "Problem",
    "ProblemKind",
    "ProviderStatus",
    "Section",
    "SensorsReport",
    "Settings",
    "Snapshot",
    "StorageReport",
    "SystemReport",
    "__version__",
    "collectors",
    "connections",
    "cpu",
    "flatten",
    "gpu",
    "health",
    "load_settings",
    "memory",
    "network",
    "section_names",
    "sections_of",
    "sensors",
    "settings",
    "snapshot",
    "storage",
    "system",
    "to_dict",
    "to_json",
]

# Library convention: emit nothing unless the application configures logging.
logging.getLogger("mabat").addHandler(logging.NullHandler())
