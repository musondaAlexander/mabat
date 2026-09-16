from __future__ import annotations

import importlib
import sys

import pytest

from mabat._shared import platform as plat
from mabat._shared.models import ProblemKind, classify_exception


def test_at_most_one_platform_flag_is_set() -> None:
    assert [plat.IS_WINDOWS, plat.IS_LINUX, plat.IS_MACOS].count(True) <= 1
    assert plat.PLATFORM_NAME


def test_optional_import_returns_module_or_none() -> None:
    assert plat.optional_import("json") is not None
    assert plat.optional_import("mabat_definitely_not_installed") is None


def test_optional_import_swallows_broken_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    def explode(name: str) -> None:
        raise RuntimeError("broken extension")

    monkeypatch.setattr(importlib, "import_module", explode)
    assert plat.optional_import("whatever") is None


def test_command_available_uses_path_lookup() -> None:
    assert plat.command_available("python") or plat.command_available("python3")
    assert not plat.command_available("mabat-no-such-binary")


def test_is_admin_returns_bool() -> None:
    assert isinstance(plat.is_admin(), bool)


def test_run_command_captures_output() -> None:
    result = plat.run_command([sys.executable, "-c", "print('hello')"])
    assert result.ok
    assert result.stdout.strip() == "hello"
    assert result.args[0] == sys.executable


def test_run_command_missing_executable() -> None:
    with pytest.raises(plat.CommandNotFoundError) as info:
        plat.run_command(["mabat-no-such-binary", "--version"])
    assert classify_exception(info.value) is ProblemKind.MISSING_DEPENDENCY


def test_run_command_timeout() -> None:
    with pytest.raises(plat.CommandTimeoutError):
        plat.run_command([sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.2)


def test_run_command_nonzero_exit_raises_unless_unchecked() -> None:
    args = [sys.executable, "-c", "import sys; sys.stderr.write('bad'); sys.exit(3)"]
    with pytest.raises(plat.CommandFailedError) as info:
        plat.run_command(args)
    assert "exited with 3: bad" in str(info.value)
    assert info.value.result.returncode == 3

    unchecked = plat.run_command(args, check=False)
    assert unchecked.returncode == 3


def test_run_command_rejects_empty_args() -> None:
    with pytest.raises(ValueError, match="executable"):
        plat.run_command([])


@pytest.mark.skipif(not plat.IS_WINDOWS, reason="PowerShell helper is Windows-only")
def test_run_powershell_on_windows() -> None:
    assert plat.run_powershell("Write-Output ok").stdout.strip() == "ok"


@pytest.mark.skipif(plat.IS_WINDOWS, reason="checks the non-Windows refusal")
def test_run_powershell_refuses_elsewhere() -> None:
    with pytest.raises(NotImplementedError):
        plat.run_powershell("Write-Output ok")
