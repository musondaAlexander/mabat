"""Memory section: system RAM and swap."""

from mabat.sections.memory.collector import memory
from mabat.sections.memory.models import MemoryReport, SwapMemory, VirtualMemory

__all__ = ["MemoryReport", "SwapMemory", "VirtualMemory", "memory"]
