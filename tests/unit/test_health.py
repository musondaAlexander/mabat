from __future__ import annotations

import json

import pytest

import mabat
from mabat import _health as health_module
from mabat._shared.serialize import to_json


def test_health_reports_core_and_optional_providers() -> None:
    report = mabat.health()
    names = {p.name for p in report.providers}
    assert {"psutil", "py-cpuinfo"} <= names
    assert report.ok  # both core providers are installed in the dev environment
    assert report.platform
    assert report.mabat_version == mabat.__version__


def test_health_serialises_cleanly() -> None:
    payload = json.loads(to_json(mabat.health()))
    assert payload["ok"] is True
    assert isinstance(payload["providers"], list)


def test_health_is_not_ok_when_a_core_provider_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health_module, "optional_import", lambda module: None)
    report = mabat.health()
    assert not report.ok
    assert all(not p.available for p in report.providers if p.required)
    assert any(p.detail.startswith("pip install") for p in report.providers)


def test_platform_specific_executables_are_marked_not_applicable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(health_module, "PLATFORM_NAME", "linux")
    statuses = {p.name: p for p in mabat.health().providers}
    assert statuses["powershell"].available is False
    assert "not applicable" in statuses["powershell"].detail
