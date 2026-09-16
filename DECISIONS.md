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
