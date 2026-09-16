from __future__ import annotations

import json
from collections import namedtuple
from types import SimpleNamespace
from typing import Any

import pytest

import mabat
from mabat._shared import platform as plat
from mabat._shared.models import ProblemKind, Problems
from mabat.sections.storage import collector, smart

Part = namedtuple("Part", "device mountpoint fstype opts")
Usage = namedtuple("Usage", "total used free percent")
IoLinux = namedtuple(
    "IoLinux", "read_count write_count read_bytes write_bytes read_time write_time busy_time"
)
IoWin = namedtuple("IoWin", "read_count write_count read_bytes write_bytes read_time write_time")


def _fake_psutil(**overrides: Any) -> SimpleNamespace:
    def disk_usage(mountpoint: str) -> Usage:
        if mountpoint == "G:\\":
            raise PermissionError("device not ready")
        return Usage(1000, 600, 400, 60.0)

    base: dict[str, Any] = {
        "disk_partitions": lambda all=False: [
            Part("C:\\", "C:\\", "NTFS", "rw,fixed"),
            Part("G:\\", "G:\\", "FAT32", "rw,removable"),
        ],
        "disk_usage": disk_usage,
        "disk_io_counters": lambda perdisk=False: {
            "sda": IoLinux(10, 20, 1024, 2048, 1500, 2500, 3000),
            "PhysicalDrive0": IoWin(1, 2, 3, 4, 5, 6),
        },
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_partitions_with_one_unreadable_volume() -> None:
    problems = Problems()
    parts = collector.read_partitions(_fake_psutil(), problems)
    assert parts is not None and [p.mountpoint for p in parts] == ["C:\\", "G:\\"]
    assert parts[0].percent == 60.0 and parts[0].total_bytes == 1000
    assert parts[1].percent is None and parts[1].total_bytes is None
    problem = problems.freeze()[0]
    assert problem.kind is ProblemKind.PERMISSION_DENIED
    assert "G:" in problem.source


def test_io_counters_convert_milliseconds_and_optional_busy() -> None:
    disks = collector.read_io(_fake_psutil(), Problems())
    assert disks is not None
    by_name = {d.name: d for d in disks}
    assert by_name["sda"].read_seconds == 1.5 and by_name["sda"].busy_seconds == 3.0
    assert by_name["PhysicalDrive0"].busy_seconds is None


def test_io_counters_empty_is_not_present() -> None:
    problems = Problems()
    assert (
        collector.read_io(_fake_psutil(disk_io_counters=lambda perdisk=False: {}), problems) == ()
    )
    assert problems.freeze()[0].kind is ProblemKind.NOT_PRESENT


# --- SMART ---------------------------------------------------------------------------


class FakeAttr:
    def __init__(self, num: int, name: str, value: int, worst: int, thresh: int, raw: str) -> None:
        self.num, self.name, self.value, self.worst, self.thresh, self.raw = (
            num,
            name,
            value,
            worst,
            thresh,
            raw,
        )


class FakeDevice:
    name = "nvme0"
    model = "Fake SSD 1TB"
    serial = "SN123"
    firmware = "1.0"
    interface = "nvme"
    size = 1_000_204_886_016
    assessment = "PASS"
    temperature = 41
    attributes = (None, FakeAttr(5, "Reallocated_Sector_Ct", 100, 100, 10, "0"), None)


def _fake_pysmart(devices: list[Any]) -> SimpleNamespace:
    return SimpleNamespace(DeviceList=lambda: SimpleNamespace(devices=devices))


def test_smart_missing_smartctl(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plat, "command_available", lambda name: False)
    problems = Problems()
    assert smart.read_smart(problems) is None
    problem = problems.freeze()[0]
    assert (problem.source, problem.kind) == ("smartctl", ProblemKind.MISSING_DEPENDENCY)
    assert "smartmontools" in problem.detail


def test_smart_missing_pysmart(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plat, "command_available", lambda name: True)
    monkeypatch.setattr(plat, "optional_import", lambda name: None)
    problems = Problems()
    assert smart.read_smart(problems) is None
    assert problems.freeze()[0].source == "pySMART"


def test_smart_devices_are_mapped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plat, "command_available", lambda name: True)
    monkeypatch.setattr(plat, "optional_import", lambda name: _fake_pysmart([FakeDevice()]))
    problems = Problems()
    devices = smart.read_smart(problems)
    assert devices is not None and len(devices) == 1
    dev = devices[0]
    assert (dev.model, dev.assessment, dev.temperature_c, dev.capacity_bytes) == (
        "Fake SSD 1TB",
        "PASS",
        41,
        1_000_204_886_016,
    )
    assert len(dev.attributes) == 1  # None slots skipped
    assert dev.attributes[0].name == "Reallocated_Sector_Ct" and dev.attributes[0].id == 5
    assert not problems


def test_smart_no_devices_explains_elevation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plat, "command_available", lambda name: True)
    monkeypatch.setattr(plat, "optional_import", lambda name: _fake_pysmart([]))
    monkeypatch.setattr(plat, "is_admin", lambda: False)
    problems = Problems()
    assert smart.read_smart(problems) == ()
    assert problems.freeze()[0].kind is ProblemKind.PERMISSION_DENIED

    monkeypatch.setattr(plat, "is_admin", lambda: True)
    problems = Problems()
    assert smart.read_smart(problems) == ()
    assert problems.freeze()[0].kind is ProblemKind.NOT_PRESENT


def test_smart_filenotfound_from_pysmart(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> None:
        raise FileNotFoundError("Command smartctl doesn't exist!")

    monkeypatch.setattr(plat, "command_available", lambda name: True)
    monkeypatch.setattr(plat, "optional_import", lambda name: SimpleNamespace(DeviceList=boom))
    problems = Problems()
    assert smart.read_smart(problems) is None
    assert problems.freeze()[0].kind is ProblemKind.MISSING_DEPENDENCY


# --- entry point ---------------------------------------------------------------------


def test_storage_without_psutil_still_tries_smart(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plat, "optional_import", lambda name: None)
    monkeypatch.setattr(plat, "command_available", lambda name: False)
    section = mabat.storage()
    assert not section.available
    assert {p.source for p in section.problems} == {"psutil", "smartctl"}


def test_storage_smart_can_be_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plat, "optional_import", lambda name: _fake_psutil())
    calls: list[str] = []
    monkeypatch.setattr(plat, "command_available", lambda name: calls.append(name))
    section = mabat.storage(smart=False)
    assert section.available and section.data is not None and section.data.smart is None
    assert calls == []


def test_storage_on_this_machine_serialises() -> None:
    section = mabat.storage()
    assert section.available
    payload = json.loads(mabat.to_json(section))
    assert payload["data"]["partitions"]
    assert all(
        set(p) >= {"device", "mountpoint", "fstype", "percent"}
        for p in payload["data"]["partitions"]
    )
