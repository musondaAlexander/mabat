# mabat

Observe your machine — CPU, GPU, memory, storage, network, sensors and OS — as plain
Python data or a CLI.

`mabat` is a **library first**: every reading is a frozen dataclass wrapped in a
`Section`, serialisable to JSON with one function, and callable from your own code —
a script, a service, a cron job. The CLI is a thin layer on top and never leaks into the
library (a guard test enforces it).

```python
import mabat

cpu = mabat.cpu()  # Section[CpuReport]: identity + a 0.5 s usage sample
cpu.data.identity.brand  # 'AMD Ryzen 5 5600H with Radeon Graphics'
cpu.data.usage.percent  # 13.2
mabat.memory().data.virtual.percent  # 60.1

snap = mabat.snapshot()  # every section, typed: snap.cpu, snap.gpu ...
snap = mabat.snapshot(only=["cpu", "memory"])  # trimmed; the rest are present but 'skipped'
snap = mabat.snapshot(skip=["sensors"], connections=True)
mabat.problems_of(snap)  # [(section, Problem), ...] for a status page
print(mabat.to_json(snap, indent=2))  # one JSON document
```

```console
$ mabat show cpu            # identity, caches, per-core usage, frequency, counters
$ mabat show memory         # RAM and swap
$ mabat show system         # OS, uptime, users, battery, busiest processes
$ mabat show storage        # partitions, disk I/O, SMART health (needs smartmontools)
$ mabat show gpu            # NVIDIA telemetry via NVML; every adapter Windows knows about
$ mabat show sensors        # temperatures, fans, power (Linux hwmon / LibreHardwareMonitor)
$ mabat show network        # interfaces, addresses, traffic; `watch network` adds live throughput
$ mabat connections         # open sockets with owning processes, netstat style
$ mabat snapshot            # one-screen overview: a status line per section
$ mabat snapshot --json --skip sensors --connections   # one document, trimmed, with sockets
$ mabat watch cpu           # live view, refreshed every second; Ctrl+C to stop
$ mabat watch snapshot -i 2 # the overview as a live dashboard
$ mabat watch memory --json # one JSON document per line (NDJSON), forever - pipe it
$ mabat cli                 # interactive mode: type `show cpu`, `watch memory`, `help`, `quit`
$ mabat health              # which data sources work here; exit 1 if a core one is missing
$ mabat config              # effective settings and which files they came from
$ mabat bench               # cold/warm latency per section against a budget
$ mabat speedtest           # bandwidth test against speedtest.net (opt-in, ~30 s, real traffic)
$ python -m mabat health    # the same CLI without the console script
```

Per-section flags on `show`, `watch` and `snapshot` (a flag that does not apply to the
section you named fails with the sections it does apply to):

```console
$ mabat show cpu --sample 0                 # non-blocking delta instead of a 0.5 s window
$ mabat show system --top 20 --sample 1     # rank more processes over a longer window
$ mabat show system --top 0                 # count only, skip the per-process scan (fast)
$ mabat show storage --no-smart --all-partitions
$ mabat show network --connections --all    # embed sockets; expand hidden interfaces
$ mabat show gpu --counters                 # Windows: load/VRAM for non-NVIDIA adapters (~5 s)
$ mabat connections --kind udp              # inet, inet4, inet6, tcp*, udp*, unix, all
```

Sharing and keeping readings:

```console
$ mabat snapshot --json --redact            # hostnames, users, addresses, serials -> "[redacted]"
$ mabat watch cpu --log cpu.ndjson          # table on screen, one JSON line per frame in the file
$ mabat history cpu.ndjson                  # replay: headline per frame, min/avg/max
$ mabat --no-color --width 100 show gpu     # global output controls; --install-completion too
```

Every command takes `--json`, and that output is byte-for-byte what the library returns.
Inside `mabat cli` every line runs through the same commands; a bare section name
(`memory`) means `show memory`.

## Install

```console
pip install -e ".[all,dev]"   # CLI + NVIDIA GPU + SMART extras + dev tooling
pip install -e .              # library only (psutil + py-cpuinfo)
pip install -e ".[cli]"       # library + the mabat command
```

Optional data sources and what they need:

| Source | Needs | Without it |
|---|---|---|
| NVIDIA GPU telemetry | `mabat[gpu]` (nvidia-ml-py) + NVIDIA driver | GPU section lists adapters from WMI only (Windows) or reports `not_present` |
| Load/VRAM for AMD or Intel adapters (Windows) | nothing to install; `--counters` or `[gpu] counters = true` (Task Manager's performance counters, ~5 s) | identity only |
| SMART disk health | `mabat[smart]` + [smartmontools](https://www.smartmontools.org) on PATH + elevated shell | storage section reports `missing_dependency` / `permission_denied` |
| Temperatures & fans on Windows | [LibreHardwareMonitor](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor) running (as Administrator for CPU sensors) | sensors section reports `missing_dependency` with this hint |
| Temperatures & fans on Linux | nothing (psutil reads hwmon) | `not_present` inside containers/VMs |
| Linux distribution name | `distro` | `distribution` is `null` |
| Bandwidth test | `mabat[speedtest]` (speedtest-cli) | `mabat speedtest` reports `missing_dependency` |

`mabat health` tells you exactly which of these are satisfied on the current machine.

## The result shape

Every section looks the same, whether or not the machine could answer:

```json
{
  "name": "gpu",
  "collected_at": "2026-09-16T14:12:39+00:00",
  "available": false,
  "data": null,
  "problems": [
    {"source": "nvml", "kind": "missing_dependency", "detail": "pip install nvidia-ml-py"}
  ]
}
```

Collectors never raise: a missing GPU, a Linux-only sensor or a denied permission becomes
a `Problem` whose `kind` (`missing_dependency`, `unsupported_platform`,
`permission_denied`, `not_present`, `backend_error`, `skipped`) tells a UI what to say, and
`data` carries whatever *was* readable. A section with data *and* problems is partial.

## Use it from your own code

The CLI is one consumer of the library, built on the same three calls your program would
use:

```python
snap = mabat.snapshot(only=["cpu", "memory"])  # collect
payload = mabat.to_dict(snap)  # the one serialisation path
rows = mabat.flatten(snap.cpu.data)  # {"identity.brand": ..., "usage.percent": ...}
```

`mabat.health()` says up front which sources the host can answer, and every
`mabat ... --json` output is exactly `mabat.to_dict(...)` of the same call, so a program
and the CLI can never disagree. Because the library never imports typer or rich, a
program can install plain `mabat` (no extras) and stay slim.

## Configuration

Tunables live in data, not code. Defaults ship in `src/mabat/_shared/defaults.toml`;
override any of them with a `mabat.toml` in the working directory, a file named by
`$MABAT_CONFIG`, or `mabat.load_settings(path)`:

```toml
[sampling]
cpu_sample_seconds = 0.5          # 0 = non-blocking delta since the previous call

[processes]
top_n = 10                        # 0 = count only, skip the per-process scan
sample_seconds = 0.5
hidden_names = ["System Idle Process"]

[thresholds]                      # what the CLI colours yellow / red
warn_percent = 80.0
critical_percent = 95.0
temperature_warn_c = 75.0
temperature_critical_c = 90.0

[network]
hidden_interface_patterns = ["Loopback*", "lo"]   # collapsed in the CLI, kept in the data
probe_address = "8.8.8.8"                        # outbound-IP probe; no packet is sent

[gpu]
counters = false                  # Windows perf counters for non-NVIDIA adapters (~5 s per call)

[redaction]
keys = ["hostname", "username", "host", "outbound_ip", "public_ip",
        "address", "local_address", "remote_address", "serial", "uuid"]
```

`mabat config` prints the effective values and every file that was consulted.

Unknown keys and wrong types are rejected with a `SettingsError` at load time.

## Security & privacy

- **No shell, ever.** External commands run only through `mabat/_shared/platform.py`:
  argument lists, mandatory timeouts, `shell=False`. The three PowerShell queries (CPU
  cache, video adapters, hardware-monitor sensors) are fixed strings in source; nothing
  from settings or user input is ever interpolated into a command. A guard test fails the
  build if `subprocess` appears anywhere else.
- **Environment variables never reach a payload.** Only `_shared/config.py` reads the
  environment (for `$MABAT_CONFIG`), and a guard plants a canary variable and checks it
  is absent from every serialised section.
- **Process command lines are never collected** (they routinely contain tokens); the
  system section reports name, user, CPU, memory, threads and start time only.
- **What *is* reported**: hostname, usernames, IP and MAC addresses, drive serials, GPU
  UUIDs — the things an observation tool exists to show. `--redact` (or `mabat.redact()`)
  replaces the fields listed under `[redaction] keys` in the settings with `"[redacted]"`
  before output, on both tables and JSON.
- **`mabat speedtest` is the one command that sends real traffic** (tens of megabytes to a
  speedtest.net server) and it only runs when you ask for it; it is never part of a snapshot.
- **The outbound-IP probe sends nothing.** It `connect()`s a UDP socket to the configured
  address and reads the local end; no datagram leaves the machine.

## Performance

Cold calls pay one-off costs that are then cached for the process: py-cpuinfo (~4 s on
Windows, it re-launches Python to run CPUID) and the WMI adapter query (~1 s). Warm
calls are sub-second everywhere except the process scan, which costs one psutil call per
process and can take seconds on hosts where security software hooks handle access.
`python scripts/bench.py` prints cold/warm timings per section against a budget; use
`top_n = 0` or `snapshot(skip=["system"])` when you do not need a process ranking.

## Layout

```
src/mabat/
  __init__.py      public API: cpu(), memory(), ..., snapshot(), health(), to_json(), settings()
  _shared/         kernel: Section/Problem models, serializer, platform helpers, settings
  sections/        one package per domain: cpu, memory, system, storage, gpu, sensors, network
  _health.py       provider availability report
  _snapshot.py     composes every section into one Snapshot; the field list is the registry
  cli/             typer app, interactive mode, rich renderers (the only place UI libraries live)
tests/
  guards/          release-blocking guard tests (user-owned; boundary, serialisation, degradation, privacy)
  unit/
scripts/           check.py (quality gates), bench.py (latency budget)
```

## Develop

```console
python scripts/check.py        # ruff format --check, ruff check, mypy --strict, pytest
python scripts/check.py --fix  # auto-format and auto-fix first
python scripts/bench.py        # per-section latency against budgets
```

[`RUNBOOK.md`](https://github.com/musondaAlexander/mabat/blob/main/RUNBOOK.md) covers installing, running, configuring, extending and
troubleshooting from a fresh clone. [`CHANGELOG.md`](https://github.com/musondaAlexander/mabat/blob/main/CHANGELOG.md) lists releases.
[`AGENT.md`](https://github.com/musondaAlexander/mabat/blob/main/AGENT.md) holds the engineering directives, [`DECISIONS.md`](https://github.com/musondaAlexander/mabat/blob/main/DECISIONS.md)
the decision log and [`BACKLOG.md`](https://github.com/musondaAlexander/mabat/blob/main/BACKLOG.md) the deferred scope.

## License

MIT - see [`LICENSE`](https://github.com/musondaAlexander/mabat/blob/main/LICENSE).
