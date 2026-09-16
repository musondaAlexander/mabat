"""System section: OS identity, uptime, users, battery and processes."""

from mabat.sections.system.collector import system
from mabat.sections.system.models import (
    Battery,
    OsIdentity,
    ProcessInfo,
    ProcessSummary,
    SystemReport,
    Uptime,
    User,
)

__all__ = [
    "Battery",
    "OsIdentity",
    "ProcessInfo",
    "ProcessSummary",
    "SystemReport",
    "Uptime",
    "User",
    "system",
]
