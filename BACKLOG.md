# BACKLOG

Ideas and scope deliberately deferred out of the current sprint. Nothing here is started
without being pulled into a sprint plan first.

## Deferred features

- **Packet capture (scapy)** — needs Npcap + Administrator on Windows and carries legal
  constraints on networks you don't own. Out of scope for an "observe my PC" tool; revisit
  only with an explicit use case.
- **Bandwidth test (speedtest-cli)** — talks to an external service and takes ~30 s; does
  not belong in a snapshot. Could be a separate opt-in command later.
- **tracemalloc / resource introspection** — profiles *your own Python code*, not the
  machine. Different tool.
- **Redaction option** — a `--redact` / `Settings.redact` switch that masks MAC addresses,
  serial numbers and usernames in serialised output before sharing a snapshot.
- **GPU utilisation for non-NVIDIA adapters on Windows** — Windows performance counters
  (`GPU Engine(*)\Utilization Percentage` via `Get-Counter`) can give a load figure for the
  Radeon iGPU; heavier than WMI static info, so deferred past Sprint 3.
- **Container / cgroup awareness** — read `/sys/fs/cgroup/{memory.max,cpu.max}` on Linux so
  numbers inside Docker reflect limits, not the host (reference doc §10).
- **History / time series** — the `watch` command keeps only the live frame; persisting
  readings (SQLite, CSV) is a separate module.
- **FastAPI and Streamlit front-ends** — documented as integrations in the hardening sprint;
  shipping them as packages (`mabat-api`, `mabat-ui`) is a later project.

- **Faster guard suite** — every `snapshot()` in `tests/guards` runs the full process scan
  (~2.5 s on a slow host). A shared session-scoped snapshot fixture, or per-section latency
  budgets, belongs in the hardening sprint.
- **Windows disk I/O time units** — psutil's `read_time`/`write_time` on Windows look
  implausibly small (≈1 s for 45 GiB read); verify the unit and, if needed, document or
  drop the columns on Windows.

## Tooling

- `pre-commit` hooks mirroring `scripts/check.py`, if commits without running the gates
  become a problem.
