"""OS identity, uptime, users, battery and processes via platform/psutil."""

from __future__ import annotations

import platform as _platform
import time
from datetime import UTC, datetime
from typing import Any

from mabat._shared import platform as plat
from mabat._shared.config import settings
from mabat._shared.models import ProblemKind, Problems, Section, attempt, now, run_collector
from mabat.sections.system.models import (
    Battery,
    OsIdentity,
    ProcessSummary,
    SystemReport,
    Uptime,
    User,
)
from mabat.sections.system.processes import read_processes

SECTION = "system"


def _timestamp(epoch: float | None) -> datetime | None:
    if not epoch:
        return None
    return datetime.fromtimestamp(epoch, tz=UTC)


def _distribution(problems: Problems) -> str | None:
    if not plat.IS_LINUX:
        return None
    distro = plat.optional_import("distro")
    if distro is None:
        problems.add("distro", ProblemKind.MISSING_DEPENDENCY, "pip install distro")
        return None
    name = attempt(problems, "distro.name", lambda: distro.name(pretty=True))
    return str(name) if name else None


def read_os(problems: Problems) -> OsIdentity:
    uname = _platform.uname()
    return OsIdentity(
        system=uname.system,
        release=uname.release,
        version=uname.version,
        platform=_platform.platform(),
        machine=uname.machine,
        hostname=uname.node,
        distribution=_distribution(problems),
        python=_platform.python_version(),
    )


def read_uptime(psutil: Any, problems: Problems) -> Uptime | None:
    boot = attempt(problems, "psutil.boot_time", psutil.boot_time)
    if boot is None:
        return None
    booted = datetime.fromtimestamp(float(boot), tz=UTC)
    return Uptime(boot_time=booted, uptime_seconds=(now() - booted).total_seconds())


def read_users(psutil: Any, problems: Problems) -> tuple[User, ...] | None:
    users = attempt(problems, "psutil.users", psutil.users)
    if users is None:
        return None
    return tuple(
        User(
            name=str(user.name),
            terminal=user.terminal or None,
            host=user.host or None,
            started=_timestamp(user.started),
            pid=getattr(user, "pid", None),
        )
        for user in users
    )


def read_battery(psutil: Any, problems: Problems) -> Battery | None:
    sensors_battery = getattr(psutil, "sensors_battery", None)
    if sensors_battery is None:
        problems.add("psutil.sensors_battery", ProblemKind.UNSUPPORTED_PLATFORM, "no battery API")
        return None
    battery = attempt(problems, "psutil.sensors_battery", sensors_battery)
    if battery is None:
        problems.add("psutil.sensors_battery", ProblemKind.NOT_PRESENT, "no battery detected")
        return None
    seconds_left = int(battery.secsleft) if battery.secsleft and battery.secsleft > 0 else None
    return Battery(
        percent=float(battery.percent),
        seconds_left=seconds_left,
        power_plugged=battery.power_plugged,
    )


def system(
    *, top_n: int | None = None, process_sample_seconds: float | None = None
) -> Section[SystemReport]:
    """OS identity, uptime, users, battery and the busiest processes.

    Process CPU figures are sampled over ``process_sample_seconds`` (settings default);
    pass ``0`` for the non-blocking delta since the previous call. ``top_n=0`` skips the
    per-process scan entirely and only counts processes - the cheap mode for callers that
    do not need a ranking.
    """
    conf = settings()
    limit = conf.top_processes if top_n is None else int(top_n)
    window = (
        conf.process_sample_seconds
        if process_sample_seconds is None
        else float(process_sample_seconds)
    )
    if limit < 0 or window < 0:
        raise ValueError("top_n and process_sample_seconds must not be negative")

    def collect(problems: Problems) -> SystemReport | None:
        os_identity = attempt(problems, "platform", lambda: read_os(problems))
        psutil = plat.optional_import("psutil")
        if psutil is None:
            problems.add("psutil", ProblemKind.MISSING_DEPENDENCY, "psutil is not installed")
            return SystemReport(os_identity, None, None, None, None) if os_identity else None
        summary = None
        if limit == 0:
            count = attempt(problems, "psutil.pids", lambda: len(psutil.pids()))
            if count is not None:
                summary = ProcessSummary(count, (), 0, 0.0, 0)
        else:
            sampled = attempt(
                problems,
                "psutil.process_iter",
                lambda: read_processes(
                    psutil, problems, window, limit, time.sleep, conf.hidden_process_names
                ),
            )
            if sampled is not None:
                top, total, inaccessible = sampled
                summary = ProcessSummary(
                    total=total + inaccessible,
                    top=tuple(top),
                    top_n=limit,
                    sample_seconds=window,
                    inaccessible=inaccessible,
                )
        return SystemReport(
            os=os_identity,
            uptime=read_uptime(psutil, problems),
            users=read_users(psutil, problems),
            battery=read_battery(psutil, problems),
            processes=summary,
        )

    return run_collector(SECTION, collect)
