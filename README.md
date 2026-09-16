# mabat

Observe your machine — CPU, GPU, memory, storage, network and OS — as plain Python
data, a CLI, or (later) an API.

`mabat` is a **library first**: every reading is a frozen dataclass wrapped in a
`Section`, serialisable to JSON with one function, and callable from your own code —
FastAPI, Streamlit, a cron job. The CLI is a thin layer on top and never leaks into the
library (a guard test enforces it).

```python
import mabat

cpu = mabat.cpu()  # Section[CpuReport]: identity + a 0.5 s usage sample
cpu.data.identity.brand  # 'AMD Ryzen 5 5600H with Radeon Graphics'
cpu.data.usage.percent  # 13.2
mabat.memory().data.virtual.percent  # 60.1
print(mabat.to_json(mabat.snapshot(), indent=2))  # everything, as JSON
```

```console
$ mabat show cpu            # identity, caches, per-core usage, frequency, counters
$ mabat show memory         # RAM and swap
$ mabat show cpu --json     # the exact payload the library returns
$ mabat health              # which data sources work here; exit 1 if a core one is missing
```

## Install

```console
pip install -e ".[all,dev]"   # CLI + NVIDIA GPU + SMART extras + dev tooling
pip install -e .              # library only (psutil + py-cpuinfo)
```

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
a `Problem` with a `kind` your UI can explain, and `data` carries whatever *was* readable.

## Configuration

Tunables live in data, not code. Defaults ship in `src/mabat/_shared/defaults.toml`;
override any of them with a `mabat.toml` in the working directory, a file named by
`$MABAT_CONFIG`, or `mabat.load_settings(path)`.

## Layout

```
src/mabat/
  __init__.py      public API: health(), snapshot(), to_json(), settings() ...
  _shared/         kernel: Section/Problem models, serializer, platform helpers, settings
  sections/        one package per domain: cpu, memory (system, storage, gpu, sensors, network to come)
  _health.py       provider availability report
  _snapshot.py     composes every section into one Snapshot
  cli/             typer app + rich renderers, one per model (the only place UI libraries are imported)
tests/
  guards/          release-blocking guard tests (user-owned)
  unit/
```

## Develop

```console
python scripts/check.py        # ruff format --check, ruff check, mypy, pytest
python scripts/check.py --fix  # auto-format and auto-fix first
```

`AGENT.md` holds the engineering directives, `DECISIONS.md` the decision log and
`BACKLOG.md` the deferred scope.
