"""Storage section: partitions, disk I/O and SMART health."""

from mabat.sections.storage.collector import storage
from mabat.sections.storage.models import (
    DiskIo,
    Partition,
    SmartAttribute,
    SmartDevice,
    StorageReport,
)

__all__ = ["DiskIo", "Partition", "SmartAttribute", "SmartDevice", "StorageReport", "storage"]
