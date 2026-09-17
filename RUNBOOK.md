# RUNBOOK

Everything needed to stand mabat up from a fresh clone, run it, extend it and fix the
usual problems — without reading the source first.

## 1. Stand it up

```console
git clone https://github.com/musondaAlexander/mabat.git
cd mabat
python -m venv venv
venv\Scripts\activate            # Windows        (Linux/macOS: source venv/bin/activate)
pip install -e ".[all,dev]" -e packages/mabat-api -e packages/mabat-ui
pre-commit install --hook-type pre-commit --hook-type pre-push   # ruff on commit, full gates on push
python scripts/check.py          # must print "all gates green"
mabat health                     # what this machine can report
```

Requirements: Python 3.12+. On Windows, PowerShell must be on PATH (it is by default);
it is used for three read-only WMI queries.

## 2. Run it

| Want | Command |
|---|---|
| one section, pretty | `mabat show cpu` |
| one section, JSON | `mabat show cpu --json` |
| everything, overview | `mabat snapshot` |
| everything, JSON, trimmed | `mabat snapshot --json --skip system,sensors` |
| live view | `mabat watch cpu -i 0.5` / `mabat watch snapshot` |
| stream JSON lines | `mabat watch network --json` |
| sockets | `mabat connections` |
| interactive | `mabat cli` then `show cpu`, `help`, `clear`, `quit` |
| per-section flags | `mabat show system --top 0`, `mabat show storage --no-smart`, `mabat show network --all` |
| share safely | add `--redact` to any command |
| keep a log | `mabat watch cpu --log cpu.ndjson`, later `mabat history cpu.ndjson` |
| settings in effect | `mabat config` |
| latency check | `mabat bench` |
| bandwidth test | `mabat speedtest` (real traffic, ~30 s, needs `mabat[speedtest]`) |
| no console script | `python -m mabat …` |

Exit status: `0` success, `1` the section (or every section of a snapshot) was unavailable,
`2` bad arguments. Piping into `head` or `Select-Object -First` is fine.

## 3. Configure it

Create `mabat.toml` in the working directory (or point `$MABAT_CONFIG` at one). Only keys
that exist in `src/mabat/_shared/defaults.toml` are accepted; the README lists them.
Typical edits:

- `top_n = 0` under `[processes]` — skip the per-process scan on slow hosts.
- `cpu_sample_seconds = 0` under `[sampling]` — non-blocking CPU readings for tight loops.
- `hidden_interface_patterns` under `[network]` — collapse VPN/VM adapters in the CLI.
- `warn_percent` / `critical_percent` under `[thresholds]` — colouring.

Changes take effect on the next process start (settings are cached per process; call
`mabat.settings.cache_clear()` to reload in-process).

## 4. Unlock optional sources

| Source | Steps | Verify |
|---|---|---|
| NVIDIA GPU | install the NVIDIA driver; `pip install "mabat[gpu]"` | `mabat show gpu` shows utilisation/VRAM |
| SMART | install [smartmontools](https://www.smartmontools.org), make sure `smartctl` is on PATH; run the terminal **as Administrator** (root on Linux); `pip install "mabat[smart]"` | `mabat show storage` shows a SMART block |
| Temperatures (Windows) | install [LibreHardwareMonitor](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor), start it as Administrator and leave it running | `mabat show sensors` lists temperatures |
| Temperatures (Linux) | nothing; needs real hardware (not a container) | `mabat show sensors` |
| Elevated details | run the terminal as Administrator/root | fewer `permission_denied` problems in `system`/`storage` |

`mabat health` reports each provider's status; `mabat snapshot` lists the first problem of
every partial section at the bottom.

## 5. Use it from other programs

- Python: `import mabat`; call `mabat.cpu()`, `mabat.snapshot(...)`, serialise with
  `mabat.to_dict` / `mabat.to_json`, flatten with `mabat.flatten`.
- HTTP: `pip install -e packages/mabat-api` then `mabat-api` (or `mabat-api --host 0.0.0.0`).
- Dashboard: `pip install -e packages/mabat-ui` then `mabat-ui` (any `streamlit run` flag passes through).
- Anything else: `mabat watch <section> --json` prints NDJSON to stdout.

## 6. Extend it — adding a section

1. `src/mabat/sections/<name>/models.py` — frozen dataclasses only (guard S4).
2. `src/mabat/sections/<name>/collector.py` — `def <name>() -> Section[Report]` built on
   `run_collector(...)`; wrap each independent reading in `attempt(...)`; return `None`
   when nothing at all was readable. Import platform helpers as
   `from mabat._shared import platform as plat` and call `plat.optional_import(...)`
   (guard D1 relies on it). Never import another section (guard R3) or `subprocess` (R6).
3. `src/mabat/sections/<name>/__init__.py` — re-export models and the collector.
4. `src/mabat/_snapshot.py` — add one field with `metadata={COLLECTOR_KEY: <name>}`
   (and `OPTIONS_KEY` if the collector takes options). Everything else — `show`, `watch`,
   `snapshot`, `mabat cli`, guards — picks it up from the field list.
5. `src/mabat/__init__.py` — export the collector and report type.
6. `src/mabat/cli/render/<name>.py` — `render_<name>(section) -> RenderableType`; wrap
   data-derived strings in `rich.text.Text`; use `DOT`/`ELLIPSIS`/`bar()` from `common`.
   Register in `cli/render/__init__.py::RENDERERS` and add a summary line in
   `cli/render/snapshot.py::SUMMARIES`.
7. `tests/unit/sections/test_<name>.py` — fake the backend; cover the degraded paths.
8. `python scripts/check.py`; update `DECISIONS.md` for any notable choice.

## 7. Release to PyPI

The package name `mabat` is registered to nobody yet; the first upload claims it.
Everything below except the accounts and the final upload is scripted.

### 7.1 One-time setup

1. Create accounts on <https://test.pypi.org> and <https://pypi.org> (both, they are
   separate) and enable two-factor authentication on each.
2. **Token route** (simplest for a first release): on each site, *Account settings ->
   API tokens -> Add token* (scope "entire account" for the very first upload; scope it to
   the project afterwards). Put them in `~/.pypirc`:

   ```ini
   [testpypi]
   username = __token__
   password = pypi-...   # the TestPyPI token

   [pypi]
   username = __token__
   password = pypi-...   # the PyPI token
   ```

3. **Trusted-Publishing route** (no tokens on your machine): after the first manual
   upload, on pypi.org open the project -> *Publishing* -> add a GitHub publisher with
   owner `musondaAlexander`, repository `mabat`, workflow `publish.yml`, environment
   `pypi`. From then on `.github/workflows/publish.yml` publishes whenever you push a
   `v*` tag.

### 7.2 Every release

```console
python scripts/check.py                  # all gates green
mabat bench                              # nothing over budget
```

1. Bump `version` in `pyproject.toml` (PyPI never accepts the same version twice) and
   move the `[Unreleased]` notes in `CHANGELOG.md` under the new version with today's date.
2. Build and validate:

   ```console
   pip install build twine
   Remove-Item -Recurse -Force dist      # rm -rf dist on Linux/macOS
   python -m build                       # dist/mabat-<version>.tar.gz + .whl
   twine check dist/*                    # README renders, metadata complete
   ```

3. Rehearse on TestPyPI, then install from it into a scratch venv:

   ```console
   twine upload -r testpypi dist/*
   python -m venv scratch; scratch\Scripts\activate    # Linux/macOS: source scratch/bin/activate
   pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple "mabat[cli]"
   mabat health && mabat show memory
   deactivate
   ```

4. Publish for real, tag, push:

   ```console
   twine upload dist/*
   git commit -am "release: v<version>"
   git tag v<version>
   git push && git push --tags           # the tag also triggers publish.yml once Trusted Publishing is set up
   ```

5. Check <https://pypi.org/project/mabat/>: description, links, classifiers, and
   `pip install mabat` from a clean venv.

CI (`.github/workflows/check.yml`) runs the gates on Windows, Ubuntu and macOS for every
push and pull request; `publish.yml` re-runs them before any upload and refuses a tag that
does not match `pyproject.toml`.

## 8. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `mabat: command not found` | venv not active | `venv\Scripts\activate`, or `python -m mabat` |
| `mabat's command line needs the 'cli' extra` | typer/rich not installed | `pip install "mabat[cli]"` |
| first `mabat show cpu` takes ~5 s | py-cpuinfo runs CPUID in a helper process on Windows | expected; cached afterwards |
| `mabat show system` takes seconds | per-process psutil calls are slow on this host (security software) | `top_n = 0` in `mabat.toml`, or `--skip system` |
| sensors: `LibreHardwareMonitor is not running` | no hardware-monitor WMI namespace | install and run LHM (section 4) |
| storage: `install smartmontools …` | `smartctl` not on PATH | install smartmontools; restart the terminal |
| storage: `smartctl found no devices; SMART needs an elevated shell` | not Administrator/root | re-run elevated |
| gpu: `not reported by this board: fan` | laptop GPUs rarely expose fan speed | expected, informational |
| `?` glyphs or `UnicodeEncodeError` in a console | legacy code page | mabat falls back to ASCII automatically; if you see errors, run `chcp 65001` or use Windows Terminal |
| `SettingsError: unknown setting` | typo in `mabat.toml` | compare against `defaults.toml` |
| tests slow | real process scan in guards | the suite pins `top_n = 0`; check `tests/conftest.py` is being picked up |
| `--top does not apply to 'cpu'` | flag given to a section that has no such option | the message lists the sections that accept it |
| speedtest: `missing_dependency` | `speedtest-cli` not installed | `pip install "mabat[speedtest]"` |
