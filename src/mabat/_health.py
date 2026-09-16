"""Which data sources work on this machine - mabat's health check.

``health()`` is cheap (no processes are spawned, nothing is sampled) and is what a
FastAPI ``/health`` endpoint or a Streamlit sidebar should call first.
"""

from __future__ import annotations

import platform as _platform
import sys
from dataclasses import dataclass, field
from datetime import datetime
from importlib import metadata

from mabat._shared.models import now
from mabat._shared.platform import PLATFORM_NAME, command_available, is_admin, optional_import

# --- data: the providers mabat knows how to use --------------------------------
# (display name, what it powers, required for the core library?)

_PYTHON_MODULES: tuple[tuple[str, str, str, bool], ...] = (
    ("psutil", "psutil", "cpu, memory, storage, network, system", True),
    ("py-cpuinfo", "cpuinfo", "cpu identity", True),
    ("nvidia-ml-py", "pynvml", "NVIDIA GPU telemetry", False),
    ("pySMART", "pySMART", "disk SMART health", False),
    ("distro", "distro", "Linux distribution name", False),
    ("speedtest-cli", "speedtest", "bandwidth test (mabat speedtest)", False),
    ("typer", "typer", "command-line interface", False),
    ("rich", "rich", "command-line rendering", False),
)

_EXECUTABLES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    # (executable, what it powers, platforms it is expected on - empty means all)
    ("smartctl", "disk SMART health (smartmontools)", ()),
    ("nvidia-smi", "NVIDIA GPU fallback", ()),
    ("powershell", "Windows WMI queries (GPU, cache, temperatures)", ("windows",)),
)


@dataclass(frozen=True, slots=True)
class ProviderStatus:
    name: str
    available: bool
    required: bool
    powers: str
    detail: str


@dataclass(frozen=True, slots=True)
class Health:
    collected_at: datetime
    mabat_version: str
    platform: str
    platform_release: str
    python: str
    is_admin: bool
    providers: tuple[ProviderStatus, ...]
    ok: bool = field(init=False)

    def __post_init__(self) -> None:
        core_ok = all(p.available for p in self.providers if p.required)
        object.__setattr__(self, "ok", core_ok)


def version() -> str:
    try:
        return metadata.version("mabat")
    except metadata.PackageNotFoundError:
        return "0+unknown"


def _module_status(name: str, module: str, powers: str, required: bool) -> ProviderStatus:
    loaded = optional_import(module)
    if loaded is None:
        return ProviderStatus(name, False, required, powers, f"pip install {name}")
    module_version = getattr(loaded, "__version__", None)
    detail = f"installed ({module_version})" if module_version else "installed"
    return ProviderStatus(name, True, required, powers, detail)


def _executable_status(name: str, powers: str, platforms: tuple[str, ...]) -> ProviderStatus:
    if platforms and PLATFORM_NAME not in platforms:
        return ProviderStatus(name, False, False, powers, f"not applicable on {PLATFORM_NAME}")
    if command_available(name):
        return ProviderStatus(name, True, False, powers, "on PATH")
    return ProviderStatus(name, False, False, powers, "not on PATH")


def health() -> Health:
    """Report the availability of every provider mabat can draw on."""
    providers = [_module_status(*entry) for entry in _PYTHON_MODULES]
    providers += [_executable_status(*entry) for entry in _EXECUTABLES]
    return Health(
        collected_at=now(),
        mabat_version=version(),
        platform=PLATFORM_NAME,
        platform_release=f"{_platform.system()} {_platform.release()}",
        python=sys.version.split()[0],
        is_admin=is_admin(),
        providers=tuple(providers),
    )
