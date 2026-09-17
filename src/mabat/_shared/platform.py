"""Platform detection, optional imports, privilege check and the ONE sanctioned subprocess site.

No other module in ``mabat`` may import ``subprocess`` (a guard test enforces it). Commands
are always argument lists - never ``shell=True`` - and always carry a timeout.
"""

from __future__ import annotations

import ctypes
import importlib
import logging
import os
import shutil
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from types import ModuleType

from mabat._shared.models import ProblemKind

log = logging.getLogger("mabat")

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")
IS_MACOS = sys.platform == "darwin"
PLATFORM_NAME = (
    "windows" if IS_WINDOWS else "linux" if IS_LINUX else "macos" if IS_MACOS else sys.platform
)


# --- optional dependencies --------------------------------------------------


def optional_import(module: str) -> ModuleType | None:
    """Import ``module`` if it is installed and importable, else ``None``.

    A broken optional dependency must never take the whole library down, so any failure
    during import is logged and treated as "not available".
    """
    try:
        return importlib.import_module(module)
    except ImportError:
        return None
    except Exception as exc:  # broad on purpose, see docstring
        log.warning("optional module %r failed to import: %s", module, exc)
        return None


def command_available(name: str) -> bool:
    """Whether an external executable is on PATH (no process is spawned)."""
    return shutil.which(name) is not None


# --- privileges ---------------------------------------------------------------


def is_admin() -> bool:
    """True when running elevated (Administrator on Windows, root elsewhere)."""
    windll = getattr(ctypes, "windll", None)  # only exists on Windows
    if windll is not None:
        try:
            return bool(windll.shell32.IsUserAnAdmin())
        except (AttributeError, OSError):
            return False
    geteuid = getattr(os, "geteuid", None)  # only exists on POSIX
    return geteuid is not None and geteuid() == 0


# --- commands -------------------------------------------------------------------


class CommandError(RuntimeError):
    """Base class for command failures; ``kind`` feeds ``Problem.from_exception``."""

    kind = ProblemKind.BACKEND_ERROR


class CommandNotFoundError(CommandError):
    kind = ProblemKind.MISSING_DEPENDENCY


class CommandTimeoutError(CommandError):
    kind = ProblemKind.BACKEND_ERROR


class CommandFailedError(CommandError):
    kind = ProblemKind.BACKEND_ERROR

    def __init__(self, message: str, result: CommandResult) -> None:
        super().__init__(message)
        self.result = result


@dataclass(frozen=True, slots=True)
class CommandResult:
    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


# Keep a console window from flashing when a GUI program spawns a helper on Windows.
_CREATION_FLAGS: int = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def run_command(args: Sequence[str], *, timeout: float = 10.0, check: bool = True) -> CommandResult:
    """Run an executable with an argument list, capturing text output.

    Raises :class:`CommandNotFoundError` if the executable is missing, :class:`CommandTimeoutError`
    if it overruns ``timeout`` seconds, and :class:`CommandFailedError` on a non-zero exit when
    ``check`` is true.
    """
    if not args:
        raise ValueError("run_command needs at least the executable name")
    argv = [str(arg) for arg in args]
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            creationflags=_CREATION_FLAGS,
        )
    except FileNotFoundError as exc:
        raise CommandNotFoundError(f"{argv[0]!r} is not installed or not on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise CommandTimeoutError(f"{argv[0]!r} did not finish within {timeout:g}s") from exc

    result = CommandResult(
        args=tuple(argv),
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
    if check and not result.ok:
        first_line = (result.stderr.strip() or result.stdout.strip() or "no output").splitlines()[0]
        raise CommandFailedError(
            f"{argv[0]!r} exited with {result.returncode}: {first_line}", result
        )
    return result


def run_powershell(script: str, *, timeout: float = 15.0) -> CommandResult:
    """Run a fixed PowerShell snippet (Windows only).

    ``script`` must come from mabat's own source, never from user input.
    """
    if not IS_WINDOWS:
        raise NotImplementedError("PowerShell helpers are only available on Windows")
    return run_command(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script], timeout=timeout
    )
