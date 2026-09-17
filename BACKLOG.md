# BACKLOG

Ideas and scope deliberately deferred out of the current sprint. Nothing here is started
without being pulled into a sprint plan first.

## Deferred features

- **Packet capture (scapy)** — needs Npcap + Administrator on Windows and carries legal
  constraints on networks you don't own. Out of scope for an "observe my PC" tool; revisit
  only with an explicit use case.
- ~~Bandwidth test (speedtest-cli)~~ — done in S8 as the opt-in `mabat speedtest`.
- **tracemalloc / resource introspection** — profiles *your own Python code*, not the
  machine. Different tool.
- ~~Redaction option~~ — done in S8: `--redact` / `mabat.redact()`, keys in `[redaction]`.
- ~~Interactive-mode line editing~~ — done in S9 with prompt_toolkit (history file,
  auto-suggest, tab completion derived from the app).
- ~~GPU utilisation for non-NVIDIA adapters on Windows~~ — done in S9: `--counters` /
  `[gpu] counters` read the GPU Engine and Adapter Memory performance counters.
- **Container / cgroup awareness** — read `/sys/fs/cgroup/{memory.max,cpu.max}` on Linux so
  numbers inside Docker reflect limits, not the host (reference doc §10).
- ~~History / time series~~ — done in S8 as `watch --log` + `mabat history` (NDJSON).
  A SQLite/CSV sink and charts remain open.
- ~~FastAPI and Streamlit front-ends as packages~~ — done in S9: `packages/mabat-api`
  and `packages/mabat-ui` (each its own distribution; publish separately).

- ~~Faster guard suite~~ — done in S6: the suite pins `[processes] top_n = 0`
  (count-only mode) and `scripts/bench.py` holds the latency budgets.
- ~~Windows disk I/O time units~~ — verified in S9: Windows psutil reports whole seconds
  (100-ns ticks / 10^7), not milliseconds; the collector now applies the right unit.

- **Verify the sensors parser against a live LibreHardwareMonitor** — built from the
  documented Hardware/Sensor WMI schema; confirm labels and parents once LHM is installed.

## Tooling

- ~~`pre-commit` hooks~~ — done in S9: ruff on commit, full gates on push
  (`.pre-commit-config.yaml`).
