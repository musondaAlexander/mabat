# DECISIONS

Dated, one-paragraph records of choices that deviated from plan, resolved an ambiguity or
introduced a pattern. Newest at the bottom.

## 2026-09-16 — Library first, CLI as a thin layer

mabat is a library whose readings must be callable from other programs (FastAPI, Streamlit)
without dragging a terminal UI along. Decided: `typer`/`rich` are an optional extra
(`mabat[cli]`) and may only be imported under `mabat/cli/`; the core depends on `psutil`
and `py-cpuinfo` alone. Enforced by the boundary guard test, not by convention.
Rejected: making typer/rich hard dependencies (simpler install, but every API service
would inherit UI packages).

## 2026-09-16 — Frozen dataclasses, not pydantic

Data models are stdlib frozen dataclasses with a single outward serialiser
(`_shared/serialize.py`). Chosen to keep the core dependency-free; FastAPI accepts
dataclasses as response models natively and Streamlit only needs dicts/dataframes.
Rejected: pydantic v2 (free JSON Schema, but a hard dependency for a benefit that only the
future API layer would use — it can wrap the dataclasses at that boundary instead).

## 2026-09-16 — One result shape: `Section[T]`

Every collector returns `Section(name, collected_at, data | None, problems, available)`.
Collectors never raise to callers: `run_collector` converts escapes into a `Problem` and
partial gaps are recorded in a `Problems` sink. `ProblemKind` distinguishes a missing
dependency, an unsupported platform, denied permission, absent hardware and backend errors
so a UI can say *why* a panel is empty. Rejected: raising exceptions (a missing GPU is not
an error for a dashboard) and returning bare `None`s (loses the reason).

## 2026-09-16 — Composition modules are private; domains live under `mabat.sections`

`mabat.health()` and `mabat.snapshot()` shadowed the modules `mabat/health.py` and
`mabat/snapshot.py`, and every domain would have hit the same clash (`mabat.cpu` package vs
`mabat.cpu()`). Decided: implementation modules are `_health.py` / `_snapshot.py`; domain
packages live under `mabat/sections/<name>/`; the public functions are re-exported from
`mabat/__init__.py`. This mirrors psutil's shape (public functions, private `_ps*` modules).

## 2026-09-16 — Snapshot field metadata is the section registry

`Snapshot` declares each section as a dataclass field whose `metadata["collector"]` is the
collector. `collectors()`, `section_names()` and `snapshot()` all derive from the field
list, so adding a domain is one field. Rejected: a decorator-based registry (import-order
magic) and a hand-maintained dict beside the dataclass (two lists to keep in sync).

## 2026-09-16 — CLI rendering lives in `cli/`, not in the domain packages

Directive §4.1 says a module owns its entry points, but a domain package registering typer
commands would import typer and break the library/UI boundary. Decided: domains own
models, collectors, providers and tests; `cli/render.py` owns one renderer per model.

## 2026-09-16 — Architecture rules are a pytest guard, not import-linter

Directive §4.3 allows "architecture tests, dependency rules, import linting". Decided on an
AST-based pytest guard (`tests/guards/test_boundaries.py`) because it also enforces rules
import-linter cannot express (subprocess only in `_shared/platform.py`, environment reads
only in `_shared/config.py`) and keeps the toolchain to ruff + mypy + pytest.

## 2026-09-16 — Settings are data (`defaults.toml`) with validated overrides

Thresholds, sample intervals, top-N counts and hidden-interface patterns ship in
`_shared/defaults.toml` and can be overridden by `./mabat.toml`, `$MABAT_CONFIG` or an
explicit path. Unknown keys and wrong types are rejected at the boundary with a
`SettingsError`. `_shared/config.py` is the only module allowed to read the environment.

## 2026-09-16 — Sprint plan adjusted after scope answers

The user chose to ship real SMART (pySMART) and LibreHardwareMonitor providers in v1
rather than seams. Cost stated and accepted: one extra sprint. Plan is now S0 Foundation,
S1 CPU + Memory, S2 System + Storage (incl. SMART), S3 GPU + Sensors (incl. LHM), S4
Network, S5 Snapshot + watch, S6 Hardening.

## 2026-09-16 — `main.py` at the repo root is a pre-project experiment

It is excluded from ruff and will be deleted in Sprint 1 once `mabat show cpu` reproduces
what it prints (including the Windows L3-cache WMI fallback).

## 2026-09-16 — Guard tests approved as drafted

The user approved `tests/guards/` (boundary R1–R7, serialisation S1–S4, degradation D1–D3,
privacy P1–P2) without changes. Hostnames, usernames, IPs and MAC addresses remain
permitted in payloads; masking them stays a backlog redaction feature. From this point the
guards may not be weakened, skipped or deleted without explicit sign-off recorded here.

## 2026-09-16 — Sections call platform helpers through the module, not bare names

Degradation guard D1 simulates missing backends by monkeypatching
`mabat._shared.platform.optional_import` / `run_command` / `run_powershell`. A section that
did `from mabat._shared.platform import optional_import` would bind its own copy and dodge
the simulation. Convention: sections write `from mabat._shared import platform as plat` and
call `plat.optional_import(...)`, so the guard exercises the real degraded path.

## 2026-09-16 — CPU identity is cached for the process lifetime

`cpuinfo.get_cpu_info()` takes ~4 s on Windows (it re-launches Python to run CPUID) and
the WMI cache query ~0.3 s. Identity cannot change while the machine is up, so both reads
are `functools.cache`d; `mabat.cpu()` costs one sample window after the first call.
`sections.cpu.identity.clear_cache()` exists for tests and hot-plug edge cases.
Rejected: a time-based cache (needless complexity for immutable data).

## 2026-09-16 — Overall CPU percent is the mean of the per-core sample

One blocking `cpu_percent(interval, percpu=True)` call feeds both the per-core list and
the overall figure, instead of a second blocking call for the aggregate. The mean of
per-core utilisation over the same window is what Task Manager shows; the difference from
psutil's own aggregate is noise. Rejected: two sequential samples (doubles latency).

## 2026-09-16 — CLI glyphs adapt to the console encoding

Block bars (U+2588/U+2591), the middle dot and the ellipsis raise `UnicodeEncodeError` on
a cp1252 console, which Windows PowerShell 5.1 still uses by default. `cli/render/common.py`
picks Unicode glyphs when `Console.encoding` is UTF-8 and ASCII (`#`, `-`, `|`, `...`)
otherwise. Rejected: forcing UTF-8 output (garbles legacy consoles) and ASCII everywhere
(ugly on modern terminals).

## 2026-09-16 — Data-derived strings are rendered as `rich.text.Text`

Rich parses `[...]` in plain strings as markup; a problem kind such as
`[missing_dependency]` or an error message with brackets silently disappeared. Any string
that originates from data (problem details, provider details) is wrapped in `Text` so it
is printed verbatim. Static labels may keep using markup.

## 2026-09-16 — Sprint 1 retrospective

Delivered: `sections/cpu`, `sections/memory`, `mabat show cpu|memory`, `main.py` retired.
Deviations: none from the plan; one kernel addition (`attempt()` and `collect` returning
`None`) turned out to be needed by every section and was added before the first one.
Learned: the Windows console encoding and Rich markup were the two real bugs, both caught
by running the CLI in a legacy console; every future renderer follows the `Text` rule.
Next sprint (S2) should reuse the `attempt()` per-reading pattern and add its renderers
under `cli/render/` from the start.

## 2026-09-16 — `watch` pulled forward from Sprint 5; renderers return renderables

The user asked for a live CPU view after Sprint 1. Cost stated: nothing in S2–S4 depends
on it, S5 shrinks to `snapshot --json` + polish; the plan stays valid. Doing it required
renderers to *return* a `RenderableType` instead of printing, so the same view feeds
`show` (print once) and `watch` (`rich.live.Live`). `watch --json` emits NDJSON, one
document per line, so the live path and the pipe path are the same collector loop.
Refresh timing is start-to-start: collection time (including a section's sample window)
is absorbed into the interval rather than added to it.

## 2026-09-16 — Process sampling is tiered; expensive attributes for the top-N only

On this Windows host each per-process psutil call costs ~5 ms (441 processes: `status`
6 s, `num_threads` 6.5 s, `memory_info` 2.4 s, `cpu_percent` 2.3 s per pass); WMI's
per-process performance class was slower still (11.7 s). Decided: one `oneshot` pass reads
CPU delta + RSS for every process, ranks them, and only the top-N pay for username,
status, threads and start time. `sample_seconds=0` skips the priming pass and relies on
psutil's `process_iter` cache for the inter-call delta. Result here: 18 s → 5.9 s
sampled, 2.5 s in delta mode; on a typical host well under a second. Rejected:
`by_status` counts (needs `status` for every process) and WMI as a Windows fast path.

## 2026-09-16 — Per-process CPU is normalised to the whole machine

`ProcessInfo.cpu_percent` divides psutil's per-core figure by the logical core count, so
100 % means the whole machine, matching Task Manager and summing sensibly with the CPU
section's overall figure. Rejected: `top`-style per-core percentages (can exceed 100).

## 2026-09-16 — Hidden pseudo-processes are settings data

"System Idle Process" would top every ranking on Windows. Its exclusion is the
`[processes] hidden_names` list in `defaults.toml`, not a string in source; it stays in
the total count.

## 2026-09-16 — SMART preconditions are reported one at a time

`read_smart` distinguishes: smartctl not on PATH (`missing_dependency`, with the
smartmontools link), pySMART not installed (`missing_dependency`), no devices while not
elevated (`permission_denied`) and no devices while elevated (`not_present`). pySMART's
own WARNING logging is silenced so problems remain the single channel.

## 2026-09-16 — Sprint 2 retrospective

Delivered: `sections/system`, `sections/storage`, renderers, `mabat show|watch
system|storage`. Deviations: none in scope; the process sampler was redesigned mid-task
after measuring the per-handle cost. Learned: measure before designing collectors that
touch every process or device; this host is a good worst case. Debt for hardening (S6):
the test suite now takes ~40 s because every `snapshot()` in the guards pays the process
scan - give the guards a cheaper snapshot fixture or a latency budget per section.

## 2026-09-16 — Interactive mode dispatches through the same Typer app

`mabat cli` (hidden alias `shell`) is a read-eval loop that shlex-splits each line and
calls the Typer app with `standalone_mode=False`, so there is exactly one command surface
to test and document. Typer 0.27 vendors click privately, so the loop does not import
click: command failures are handled by duck typing (`exc.show()`, `exc.exit_code`) and
any other exception is printed and swallowed - nothing can kill the session. A bare
section name is rewritten to `show <section>` as a convenience. Rejected: a separate
`cmd.Cmd` subclass with its own verbs (a second surface that would drift from the CLI).

## 2026-09-16 — GPU: NVML per-reading guards, WMI for everything else, merged by name

Boards differ in what NVML exposes (this laptop rejects fan speed), so every NVML getter is
guarded individually and the unsupported ones are reported as one `not_present` problem
rather than blanking the section. On Windows `Win32_VideoController` is the only way to
see non-NVIDIA adapters; its rows are cached per process (~1 s per PowerShell launch) and
merged with NVML devices by case-insensitive name, NVML data winning. `PNPDeviceID`
starting with `PCI\` marks physical adapters; virtual displays are kept but flagged.
Rejected: hiding virtual adapters (a user observing their PC should see what Windows
sees) and per-call WMI queries (`watch gpu` would cost a PowerShell launch per frame).

## 2026-09-16 — Sensors: one PowerShell launch probes both hardware-monitor namespaces

There is no built-in Windows API for CPU temperature; LibreHardwareMonitor (and the older
OpenHardwareMonitor) publish identical WMI schemas while running. A single fixed PowerShell
script tries both namespaces and reports which answered, halving the cost of the common
"not running" answer (2.0 s → 0.8 s) and keeping the Python side to one parse path.
"Invalid namespace" means not running (`missing_dependency` with install guidance); any
other error is a `backend_error`. Temperature colouring uses the sensor's own critical
limit when present (warning from 85 % of it), else `[thresholds] temperature_*_c` from
`defaults.toml`. Rejected: a TTL cache for the negative result (a monitor started
mid-session would go unnoticed).

## 2026-09-16 — Sprint 3 retrospective

Delivered: `sections/gpu`, `sections/sensors`, renderers, `show|watch gpu|sensors`.
Deviations: none. Learned: probing the real NVML/WMI surface before modelling paid off
(the model matches what the board actually reports); the sensors section is correct but
unverified against a live LibreHardwareMonitor - the parser is tested on a captured
payload shape and should be re-checked once LHM is installed. Test suite: ~47 s.
