# AGENT.md — Development Directives

> **Purpose:** This document directs AI-assisted development on this project. It is portable and language-independent. Drop it into any repository (new or existing) and instruct the agent to read it before doing anything else. Where a rule references tooling, use the idiomatic equivalent for this project's stack.

> **Precedence:** These directives override the agent's defaults. If a user instruction conflicts with this document, flag the conflict before proceeding. If this document conflicts with itself or with reality in the repo, stop and ask.

---

## 0. First Contact Protocol (Before Any Work)

Before writing a single line of code, the agent must establish context. Never assume; verify.

### 0.1 New Project
1. Read this document fully.
2. Read the project concept/requirements document if one exists. If none exists, ask for one or ask the questions in Section 5 to build one.
3. Confirm the stack, then map every generic rule in this document to concrete tooling (formatter, static analyzer, test framework, module system) and state the mapping back to the user for approval.
4. Do not scaffold until the user approves the mapping and the sprint plan.

### 0.2 Existing Project
1. Read this document fully.
2. Ask the user for links or paths to the relevant local repositories, related services, or prior documentation needed for context. Do not guess at conventions that can be observed.
3. Explore before proposing: directory structure, existing module boundaries, dependency manifest, test suite state, existing standards config (linters, formatters, CI).
4. Produce a short **Context Report** back to the user: what the project is, how it is structured, what conventions it follows, what state the tests are in, and any conflicts between the existing codebase and this document.
5. Where the existing codebase conflicts with these directives, do not silently refactor. List the conflicts, propose a migration approach, and wait for a decision.

---

## 1. Code Standards

Language-independent rules; map each to the stack's idiomatic tools in Sprint 0.

### 1.1 Consistency Is Enforced, Not Requested
- A formatter and a static analyzer are configured in Sprint 0 and run in CI. Code that fails either is not done.
- Follow the established conventions of the stack and of the existing codebase. Boring and idiomatic beats clever and novel. Introduce a new pattern only with explicit approval, recorded in `DECISIONS.md`.

### 1.2 Structure
- Thin entry points (controllers/handlers/routes), business logic in dedicated action/service units, validation at the boundary, authorization as explicit policy checks — never inline role/permission conditionals scattered through logic.
- One serialization path outward. Internal models/entities are never exposed directly to any external interface (API response, file export, UI). This is how privacy and contract stability are guaranteed structurally.
- Configuration over code: anything an administrator or operator might one day change lives in data (database, config store, seed files), not in source. Domain vocabulary (categories, types, statuses visible to users) is data unless there is a strong argued reason otherwise.

### 1.3 State and Trust
- Anything with a lifecycle (approval, verification, publication, payment) is modeled as an explicit state machine with defined transitions. Invalid transitions are rejected with a clear error, never silently ignored.
- Every privileged or trust-relevant action (approve, suspend, delete, verify, refund) writes an audit record: actor, action, subject, reason, timestamp.
- Sensitive data is protected by architecture, not discipline: private storage, authorized access paths, and a permanent test proving the data cannot appear where it must not.

### 1.4 Data
- Every foreign relationship constrained. Every hot query path deliberately indexed. Migrations/schema changes are append-only once merged; mistakes are fixed forward.
- Soft-delete user-generated content; hard-delete only via explicit, audited purge routines.

### 1.5 Errors and Boundaries
- One consistent error shape across the whole external surface, with correct status/error codes.
- All external input validated at the boundary. No raw input reaches a query, a file path, or a shell.
- Rate limiting on public and authentication surfaces.

### 1.6 Observability (From Sprint 0, Not Sprint Last)
- Error tracking, health-check endpoint, and background-job/queue monitoring are part of the foundation sprint of every project.
- Significant domain actions emit events/log entries from day one, even if no report consumes them yet. Recording is cheap; retrofitting is not.

---

## 2. Sprint Approach

### 2.1 Structure
- Work is organized into **module-based sprints**: one sprint delivers one module (or one coherent slice of one), in an explicitly ordered dependency chain. A dependency map is part of every sprint plan.
- Sprint 0 is always Foundation: scaffolding, standards tooling, CI, base error shape, observability, and this document's stack mapping.
- Never start a sprint early because it looks easy. Never expand scope mid-sprint; new ideas go to a `BACKLOG.md`, not into the current sprint.

### 2.2 Sized for Agent Sessions
- Each sprint is broken into **3–5 tasks**, each completable within a single focused session. After each task: tests green → commit → checkpoint.
- If context is getting long or quality is degrading, stop at a checkpoint and recommend a fresh session rather than pushing through. State clearly where work stopped and what the next task is.
- At the start of any session on an in-progress project, re-read this document, `DECISIONS.md`, and the current sprint's task list before touching code.

### 2.3 Definition of Done (Every Sprint)
- [ ] All planned tasks complete and committed at checkpoints
- [ ] Full test suite green (not just new tests)
- [ ] Formatter and static analyzer clean
- [ ] New endpoints/interfaces documented
- [ ] Domain events emitted for new significant actions
- [ ] No domain vocabulary hardcoded (automated check where possible)
- [ ] Release-blocking guard tests (Section 3.2) still green
- [ ] `DECISIONS.md` updated with any deviations or notable choices
- [ ] This document updated if the sprint invalidated any part of it

### 2.4 Post-Sprint Update Pass
A stale directive is worse than none. At the end of every sprint, the agent proposes updates: what deviated from plan, what was learned, what the next sprint should account for. The user approves; the documents stay honest.

---

## 3. Verification and Trust Boundaries

The engineer's role in agent development is auditor, not just author. This section encodes that.

### 3.1 The Agent Does Not Audit Itself Alone
- The agent writes most tests, but **release-blocking guard tests are owned by the user**: the agent drafts them first, presents them for line-by-line review, and the user approves before implementation begins. Once approved, these tests may not be modified without explicit user sign-off — weakening a guard test to make a feature pass is a violation, not a fix.

### 3.2 Release-Blocking Guard Tests (Per Project, Defined in Sprint 0)
Typical candidates — adapt per project:
- Privacy guards: sensitive fields can never appear in public/external payloads.
- State machine guards: invalid transitions are rejected.
- Authorization guards: every policy's *forbidden* case returns the correct denial.
- Boundary guards: module isolation rules (see 4.3) hold.

### 3.3 Human-Eyes List
The agent flags, and the user personally reviews, every change touching:
- Authorization/permission logic
- Anything handling money or payments
- Anything handling private documents or sensitive personal data
- Schema migrations
- The guard tests themselves
Everything else is trusted to the automated gates.

---

## 4. Modularization (Core Concept)

### 4.1 Boundaries Are the Architecture
- The system is composed of modules with explicit responsibilities, listed in a module table in the project's sprint plan. Each module owns its routes/entry points, business logic, data definitions, and tests.
- Prefer a modular monolith over premature service-splitting. Clean internal boundaries preserve the option to split later; distributed complexity is never adopted by default.

### 4.2 Communication Rules
- Modules talk through defined interfaces or domain events — never by reaching directly into another module's internals (models, tables, private services).
- Shared code lives in one small, deliberate shared area. If the shared area is growing fast, that is a design smell to flag.

### 4.3 Boundaries Are Enforced, Not Documented
- Module isolation rules are encoded as executable checks (architecture tests, dependency rules, import linting — whatever the stack supports) and run in CI. An agent has no embarrassment reflex about crossing a boundary; the check is the reflex.

### 4.4 Seams for the Future
- Deferred features get interfaces, not implementations: define the seam (e.g., a payment gateway interface, a matching engine interface, a notification channel abstraction) and bind a null/simple implementation. Do not speculatively build.
- Design dimensions for known expansion (multi-tenancy, multi-country, localization) as cheap columns/flags now rather than migrations later — but only the dimensions the concept document actually names.

---

## 5. Clarify Before Building

### 5.1 Ask, Don't Assume
When requirements are ambiguous, conflicting, or silent on something consequential, the agent asks **before** implementing. Consequential means: data model shape, module boundaries, security/privacy behavior, external contracts, anything expensive to reverse.

### 5.2 Standard Clarifying Questions (Use What Applies)
- Who are the distinct actors, and can one person be more than one of them?
- What must be true for this feature to be *trusted* (verification, audit, moderation)?
- What is public vs. authenticated vs. privileged?
- What is deferred but planned (payments, ratings, other regions)? → these get seams.
- What here is domain vocabulary that admins should control as data?
- What are the realistic volumes (users, records, requests) for index and cache decisions?
- For existing projects: are there conventions or constraints not visible in the repo?

### 5.3 Small Ambiguities
For minor gaps not worth an interruption, choose the most reasonable option, implement it, and **state the assumption explicitly** in the output and in `DECISIONS.md`. Never bury an assumption silently in code.

---

## 6. Context Capture

### 6.1 Gathering Context
- At project start (and whenever a task references systems the agent hasn't seen), ask the user for paths/links to local repositories, related services, prior specs, or API contracts that hold relevant context. Read them before proposing designs that must interoperate with them.
- When given a repository for context, produce a brief summary of what was learned from it so the user can correct misreadings early.

### 6.2 Maintaining Context Artifacts
Every project carries three living documents, kept in the repo root:
- **This file (AGENT.md):** the directives. Updated when reality invalidates it.
- **DECISIONS.md:** dated, one-paragraph decision records — what was decided, why, what was rejected. Written whenever a choice deviates from plan, resolves an ambiguity, or introduces a pattern.
- **BACKLOG.md:** ideas and scope deferred out of the current sprint.

### 6.3 Session Continuity
- End every working session with a short status block: current sprint, tasks done, next task, any open questions. Begin every session by reading the previous status block.

---

## 7. Git and Commit Discipline

- **No AI co-authorship attribution.** Commit messages must not include `Co-Authored-By: Claude`, "Generated with Claude Code", robot emojis, or any AI attribution lines or trailers. Commits are authored by the user, full stop.
- Conventional, imperative commit messages scoped to the module: `feat(verification): add rejection with mandatory reason`, `fix(search): correct location filter index`, `test(directory): add privacy guard for public payloads`.
- Commit at every task checkpoint — small, coherent, passing commits. Never commit failing tests; never bundle unrelated changes.
- Never force-push, rewrite published history, or delete branches without explicit instruction.

---

## 8. Scope and Finishing Discipline

Starting is cheap with an agent; finishing is the scarce resource. These rules protect completion:

- The current sprint plan is the scope. The agent does not propose or begin adjacent features, rewrites, or "while we're here" improvements mid-sprint; it records them in `BACKLOG.md`.
- If the user requests new scope mid-sprint, the agent may implement it but must first state the cost: what it displaces or delays, and whether it invalidates the sprint plan.
- "Done" means deployed-ready per the Definition of Done, including documentation and observability — not merely "the feature works on the happy path."
- Every project's final sprint is a hardening sprint: documentation pass, index/performance review with realistic data volume, security sweep, deployment runbook. A new developer or a fresh agent session should be able to stand the system up from the runbook alone.

---

## 9. Project-Specific Mapping (mabat)

| Directive | Concrete Choice for This Project |
|---|---|
| Language / framework | Python 3.12, `src/` layout, package `mabat`; library first, CLI via optional extra `mabat[cli]` |
| Formatter | `ruff format` |
| Static analyzer | `ruff check` (incl. bandit `S`, no-print `T20`) + `mypy --strict` over `src`, `tests`, `scripts` |
| Test framework | `pytest` (`guard` marker for release-blocking tests) |
| Module system | `mabat/_shared/` kernel; one package per domain under `mabat/sections/`; `_health.py` and `_snapshot.py` compose; `mabat/cli/` renders |
| Boundary enforcement | `tests/guards/test_boundaries.py` (AST import rules) run by `scripts/check.py` and CI |
| Auth mechanism | N/A — local library/CLI; no network surface |
| Error shape | `Section[T]` with `data`, `available`, `problems: tuple[Problem]`; collectors never raise |
| Error tracking | `logging.getLogger("mabat")`; collectors log at debug/warning; applications attach handlers |
| Health check | `mabat.health()` / `mabat health` (exit 1 when a core provider is missing) |
| Queue/job monitoring | N/A — no background jobs |
| Configuration as data | `_shared/defaults.toml` + `./mabat.toml` / `$MABAT_CONFIG` overrides, validated by `_shared/config.py` |
| Guard tests (list) | boundary (no UI deps in core, sections isolated, subprocess/env confined); serialisation (every section → JSON, foreign objects rejected); degradation (collectors survive missing backends); privacy (no env vars, cmdlines or secrets in payloads) |
| Human-eyes paths (list) | `tests/guards/`, `src/mabat/_shared/serialize.py`, `src/mabat/_shared/platform.py`, the three `run_powershell` call sites (cpu/identity.py, gpu/wmi.py, sensors/providers.py) |
| Latency budget | `python scripts/bench.py` (warm-call budgets per section; run before release) |
| Runbook | `RUNBOOK.md` (stand up, run, configure, unlock sources, extend, release, troubleshoot) |
| Not applicable | §1.3 state machines & audit records, §1.4 database rules, §1.5 rate limiting (read-only local observation, no persistence) |

### Sprint plan

| Sprint | Delivers | Depends on |
|---|---|---|
| S0 Foundation ✅ | scaffold, gates, `_shared`, health, snapshot skeleton, CLI stub, guard drafts | — |
| S1 CPU + Memory ✅ | `sections/cpu`, `sections/memory`, `mabat show cpu\|memory` | S0 |
| S2 System + Storage ✅ | OS identity, uptime, users, battery, top-N processes; partitions, usage, I/O, SMART (pySMART) | S0 |
| S3 GPU + Sensors ✅ | NVML + WMI-static GPU providers; LibreHardwareMonitor WMI temps/fans provider + null | S0 |
| S4 Network ✅ | interfaces, addresses, link stats, counters, outbound IP, connections behind a flag | S0 |
| S5 Snapshot + polish ✅ | `mabat snapshot --json`, `watch snapshot`, `python -m mabat`, polish | S1–S4 |
| S6 Hardening ✅ | README integration section, latency budget (`scripts/bench.py`), subprocess security sweep, RUNBOOK.md | S5 |
| S7 CLI completeness ✅ | per-section flags, `--all`, `--kind`, `config`, `bench`, completion, `--no-color`/`--width`, branded interactive mode, watch session stats | S6 |
| S8 Backlog features ✅ | `--redact`, `watch --log` + `history`, `speedtest` | S7 |
| S9 Remaining items ✅ | GPU perf counters for non-NVIDIA adapters, prompt_toolkit line editing, macOS CI, Windows disk time units, pre-commit | S8 |

---

## 10. When in Doubt

- Prefer boring, well-trodden conventions over cleverness.
- Prefer a data-driven design over a code change for anything an admin might change.
- Prefer an interface seam over a speculative implementation.
- Prefer stopping at a clean checkpoint over pushing through a degrading session.
- Prefer asking over assuming — and when assuming anyway, say so out loud and write it down.
