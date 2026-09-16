"""Memory models: system RAM and swap. All sizes in bytes."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VirtualMemory:
    """``available`` is what psutil recommends for "how much can I still allocate";
    ``other`` carries platform buckets (``buffers``/``cached``/``shared`` on Linux,
    ``wired``/``inactive`` on macOS)."""

    total_bytes: int
    available_bytes: int
    used_bytes: int
    free_bytes: int
    percent: float
    other_bytes: dict[str, int]


@dataclass(frozen=True, slots=True)
class SwapMemory:
    """``swapped_in``/``swapped_out`` are cumulative since boot (page-file activity on
    Windows)."""

    total_bytes: int
    used_bytes: int
    free_bytes: int
    percent: float
    swapped_in_bytes: int
    swapped_out_bytes: int


@dataclass(frozen=True, slots=True)
class MemoryReport:
    virtual: VirtualMemory | None
    swap: SwapMemory | None
