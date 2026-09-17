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

## 2026-09-16 — Network throughput is computed between calls in-process

Counters are cumulative, so rates need two samples. Rather than blocking for a window,
`network()` remembers the previous counters per interface (and the system total) and
reports throughput since the last call in this process; the first call yields
`rates=None`. This gives `watch network` a true rate per frame at zero extra latency and
costs nothing for one-shot calls. Counter resets and clock regressions yield `None`.
Rejected: a blocking sample window (adds latency to every snapshot for a number most
callers do not need).

## 2026-09-16 — Connections are opt-in and also a standalone section

The socket table is large (1,100 rows here), noisy and needs elevation on macOS, so it
is excluded from `snapshot()` and from plain `network()`. `network(connections=True)`
embeds it for API consumers; `mabat.connections()` / `mabat connections` return just the
table for the netstat use case. Owning process *names* are resolved (cheap); command
lines are never collected (privacy guard P2). The implementation module is `sockets.py`
so the package can re-export the `connections()` function without shadowing a module.

## 2026-09-16 — Sprint 4 retrospective

Delivered: `sections/network`, `mabat show|watch network`, `mabat connections`, broken-
pipe handling in the entry point. Deviations: none. Learned: Windows adapter names are
long; 80-column layouts need explicit column budgets (`min_width`, `overflow="fold"`)
rather than letting Rich guess. All seven planned sections now exist; S5 is composition
and polish, S6 hardening.

## 2026-09-16 — Snapshot selection keeps the shape; options route by field metadata

`snapshot(only=..., skip=...)` never removes fields: sections left out are present with
`available=False` and a `skipped` problem, so FastAPI/Streamlit consumers get a stable
schema whatever the caller trimmed. Collector options are declared on the `Snapshot`
field (`OPTIONS_KEY`), and `snapshot(**options)` routes each one only to collectors that
declared it - today `connections` -> `network`. Rejected: an `Optional` field per
section (breaks the "one shape" promise) and special-casing network in the composer.

## 2026-09-16 — One `Target` serves show, watch and snapshot

`show`, `watch` and `snapshot` all resolve a name to a `Target` (collect + render +
availability), with `snapshot` as a first-class target. Adding a command-level view
therefore never duplicates collection or rendering logic. The overview renderer keeps one
summary function per section in a dict, mirroring `RENDERERS`.

## 2026-09-16 — Tests neutralise colour-forcing environment variables

Rich honours `FORCE_COLOR` at console creation; a developer shell exporting it made every
CLI assertion see ANSI codes. `tests/conftest.py` clears `FORCE_COLOR`/`CLICOLOR_FORCE`/
`TTY_COMPATIBLE` and sets `NO_COLOR` before `mabat.cli` is imported.

## 2026-09-16 — Sprint 5 retrospective

Delivered: `snapshot(only/skip/**options)`, `problems_of`, `mabat snapshot` overview and
JSON, `watch snapshot`, `python -m mabat`, interactive-mode hint when core providers are
missing. Deviations: none. Learned: `__main__.py` must guard `main()` behind
`__name__ == "__main__"` or the frozen-model guard (which imports every library module)
runs the CLI. Suite is now ~60 s; the hardening sprint addresses it.

## 2026-09-16 — `top_n = 0` is the cheap mode for the system section

The per-process scan dominates every snapshot on hosts where handle access is slow. With
`top_n = 0` the collector only counts processes (`psutil.pids()`, one call) and skips the
scan; the test suite pins it and dropped from ~60 s to ~29 s. Callers that want the
ranking keep the default. Rejected: caching process results across calls (stale rankings
are worse than slow ones) and a session-scoped test fixture (would exercise a fake path).

## 2026-09-16 — Latency budgets live in `scripts/bench.py`

Warm-call budgets per section (cpu 1.5 s, memory 0.2 s, system 10 s, storage 3 s, gpu
1.5 s, sensors 3 s, network 1 s, snapshot 20 s) are deliberately generous: they catch a
collector that starts spawning a process per call, not slow hardware. Cold calls are
reported, not judged. Not run in CI (runner variance); run before a release.

## 2026-09-16 — `probe_address` must be an IP literal

The outbound-IP probe promises to send nothing. A hostname in `[network] probe_address`
would trigger a DNS query, so settings now reject anything `ipaddress.ip_address` cannot
parse. Security sweep result: three PowerShell call sites (cpu cache, video adapters,
hardware-monitor sensors), all fixed strings, all through `_shared/platform.py`, all with
timeouts; no settings value reaches a command line.

## 2026-09-16 — Sprint 6 retrospective (hardening)

Delivered: cheap process mode, latency benchmark, FastAPI and Streamlit examples, README
rewrite (integration, security & privacy, performance), RUNBOOK.md, CI snapshot smoke,
probe-address validation. Deviations: none. The project is feature-complete for its v1
scope; remaining items are in BACKLOG.md (live LibreHardwareMonitor verification,
redaction, Radeon utilisation, cgroup awareness, history). Version left at 0.1.0 for the
owner to bump at release.

## 2026-09-16 — Sprint 7: CLI flags route through the same metadata as snapshot options

`--sample`, `--top`, `--all-partitions`, `--no-smart` and `--connections` map to collector
options in one table (`cli/targets.py::FLAGS`); which sections accept an option still comes
from the `Snapshot` field metadata. A flag given to a section that accepts none of its
options exits 2 and names the sections that do. `--sample` deliberately feeds both the
CPU window and the per-process window. Rejected: per-command option subsets (drift) and
silently ignoring misapplied flags (hides typos).

## 2026-09-16 — Sprint 7: `mabat config`, `mabat bench`, session stats, branding

`resolve_settings()` returns every source consulted (defaults, `./mabat.toml`,
`$MABAT_CONFIG`, explicit) with an applied flag; `mabat config` renders it - the fastest
route to a `SettingsError`. The benchmark moved into `cli/bench.py` (`scripts/bench.py` is
a wrapper) so budgets ship with the package. `watch` tracks one headline number per
section (`cli/stats.py`) and prints min/avg/max per frame. Interactive mode opens with a
wordmark - block art on UTF-8 consoles, figlet-style ASCII elsewhere - plus version and
host; `clear` redraws it. Shell completion is enabled; `--no-color`/`--width` are global.

## 2026-09-16 — Sprint 8: redaction acts on the models, keys are data

`mabat.redact()` walks frozen dataclasses (and dicts/lists) replacing string fields whose
*name* is in `[redaction] keys` with `"[redacted]"`, so tables and JSON agree and no
second serialisation path exists. `User.name` was renamed `User.username` so the key list
can name identities without catching process or interface names. Rejected: hashing
values (IPv4 space is brute-forceable) and type-specific redaction (code, not data).

## 2026-09-16 — Sprint 8: `watch --log` + `history` share the headline extractor

Headlines are read from JSON payloads (`to_dict` output) rather than models, so a live
frame and a replayed log line use the same `cli/stats.py` code. `--log` appends NDJSON
while the table stays on screen; `history` replays it with per-frame values and
min/avg/max. Rejected: a SQLite sink (a file of JSON lines needs no schema and any tool
can read it).

## 2026-09-16 — Sprint 8: speedtest is a standalone section, never in a snapshot

`mabat speedtest` / `mabat.speedtest()` wrap `speedtest-cli` behind the `speedtest` extra.
It moves real traffic and takes ~30 s, so it is not registered on `Snapshot` and has no
place in `watch`. Verified live: 5.2 Mbit/s down, 3.1 up, 263 ms; `public_ip` is a
redaction key. Failures (offline, service unreachable) are one `backend_error` problem.

## 2026-09-16 — Sprints 7 and 8 retrospective

Delivered everything listed as "remaining in the CLI": per-section flags, `--all`,
`--kind`, `config`, `bench`, completion, `--no-color`/`--width`, branded interactive mode
with `clear`, watch session stats, `--redact`, `--log` + `history`, `speedtest`.
Not done: command history / tab completion inside `mabat cli` on Windows (needs
prompt_toolkit or pyreadline3 - left in BACKLOG.md). Suite: 269 tests, ~34 s.

## 2026-09-16 — GPU load for non-NVIDIA adapters via Windows performance counters, opt-in

Task Manager's GPU figures come from ``GPU Engine(*)\Utilization Percentage`` (one
instance per process x adapter x engine) and ``GPU Adapter Memory(*)``; adapters are
LUIDs, mapped to names and dedicated totals through ``HKLM\SOFTWARE\Microsoft\DirectX``
(restricted to LUIDs present in the counters, because the registry keeps stale entries
from earlier boots). Headline utilisation is the busiest engine type, like Task Manager;
the per-engine breakdown is kept. Rate counters need two samples a second apart, so one
call is ~3-6 s: the reading is opt-in (``gpu(counters=True)``, ``--counters``, or
``[gpu] counters = true``) and NVML keeps precedence for NVIDIA boards. Aggregation is
done inside the PowerShell script so the payload is a dozen numbers, not 600 instances.
Rejected: enabling it by default (would make every snapshot 5 s slower on this host).

## 2026-09-17 — Sprint 9: interactive-mode line editing via prompt_toolkit

``mabat cli`` uses a prompt_toolkit ``PromptSession`` when stdin and stdout are terminals:
persistent history in ``~/.mabat_history``, history auto-suggest, and tab completion whose
tree is derived from the Typer app (commands -> targets -> flags) and filtered by the same
metadata the CLI uses to reject misapplied flags, so completion never offers something
the command would refuse. Without a terminal, or without the package, the loop falls back
to plain ``input()`` so tests and pipes behave identically. Cost accepted: prompt_toolkit
(2.9 MiB, one dependency) joins the ``cli`` extra. The session is verified headlessly
through prompt_toolkit's pipe input. Rejected: pyreadline3 (Windows-only, unmaintained).

## 2026-09-17 — Sprint 9: companion packages instead of examples

``packages/mabat-api`` (FastAPI, ``mabat-api`` script) and ``packages/mabat-ui``
(Streamlit, ``mabat-ui`` script) are separate distributions in the same repository,
depending on ``mabat`` and nothing in its internals; they return ``mabat.to_dict(...)``
so the API and CLI cannot disagree. The dashboard body is a ``st.fragment(run_every=...)``
rather than sleep + rerun, which keeps the sidebar responsive and lets ``AppTest`` run it
headlessly. Their tests and type checks are part of the root gates; CI installs both.
``examples/`` was removed. Publishing them is a separate ``twine upload`` per package.

## 2026-09-17 — Sprint 9: Windows disk I/O times are seconds, not milliseconds

psutil documents ``read_time``/``write_time`` as milliseconds and they are on Linux and
macOS; on Windows the values matched ``Win32_PerfRawData_PerfDisk_PhysicalDisk``'s
100-ns counters divided by 10^7, i.e. whole seconds. The storage collector now applies a
platform unit, turning "0m 01s" for 47 GiB into the real 19 min. Rejected: dropping the
column on Windows (the figure is right once scaled).

## 2026-09-17 — Sprint 9: CI covers macOS; pre-commit mirrors the gates

``macos-latest`` joined the matrix; no test needed changing (socket listing already
tolerates ``permission_denied``). ``.pre-commit-config.yaml`` runs ruff on commit and the
full ``scripts/check.py`` on push, using the venv's own tools (``language: system``) so
there is one definition of "green".

## 2026-09-17 — Hooks re-exec into the repository venv

The first push from VS Code was rejected by the new pre-push hook: the GUI's git runs
without the venv on PATH, so the gates ran under the global interpreter and mypy could
not see the project's dependencies. ``scripts/check.py`` now detects a foreign
interpreter (no ``mabat``/``ruff``/``mypy``/``pytest``) and re-runs itself with
``venv/`` or ``.venv/`` at the repo root, and invokes every tool as ``python -m`` so a
global ruff can never pair with a venv mypy. Both hooks route through the script
(``--quick`` for the commit stage). Rejected: ``language: python`` hooks with
``additional_dependencies`` (a second, drifting copy of the toolchain).
