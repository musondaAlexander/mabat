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
from mabat.sections.storage import StorageReport, storage
from mabat.sections.system import SystemReport, system

__version__ = version()

__all__ = [
    "CpuReport",
    "GpuReport",
    "Health",
    "MemoryReport",
    "Problem",
    "ProblemKind",
    "ProviderStatus",
    "Section",
    "Settings",
    "Snapshot",
    "StorageReport",
    "SystemReport",
    "__version__",
    "collectors",
    "cpu",
    "flatten",
    "gpu",
    "health",
    "load_settings",
    "memory",
    "section_names",
    "sections_of",
    "settings",
    "snapshot",
    "storage",
    "system",
    "to_dict",
    "to_json",
]

# Library convention: emit nothing unless the application configures logging.
logging.getLogger("mabat").addHandler(logging.NullHandler())
