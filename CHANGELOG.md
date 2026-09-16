# Changelog

All notable changes to mabat. The format follows [Keep a Changelog](https://keepachangelog.com/);
versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-09-16

First release.

### Library
- Seven sections as frozen dataclasses behind one `Section` result shape: `cpu`, `memory`,
  `system`, `storage`, `gpu`, `sensors`, `network`; plus standalone `connections()` and
  `speedtest()`.
- `snapshot(only=..., skip=..., **options)` composing every section; `problems_of()`.
- One serialisation path: `to_dict()`, `to_json()`, `flatten()`; `redact()` for sharing.
- Collectors never raise: missing backends, unsupported platforms and denied permissions
  become typed `Problem`s.
- Settings in data (`defaults.toml`, overridable by `mabat.toml` / `$MABAT_CONFIG`);
  `resolve_settings()` reports every source consulted.
- Windows providers: WMI fallbacks for CPU cache sizes and video adapters, NVML for
  NVIDIA GPUs, LibreHardwareMonitor's WMI namespace for temperatures and fans.

### Command line
- `show`, `snapshot`, `watch` (live view, NDJSON streaming, `--log`), `history`,
  `connections`, `health`, `config`, `bench`, `speedtest`, `version`.
- Interactive mode `mabat cli` with a branded banner, `help`, `clear`, `quit`.
- Per-section flags (`--sample`, `--top`, `--all-partitions`, `--no-smart`,
  `--connections`, `--all`, `--kind`), `--redact` everywhere, `--json` everywhere,
  `--no-color`, `--width`, shell completion.

### Integrations
- `examples/fastapi_app.py` and `examples/streamlit_app.py`.

[Unreleased]: https://github.com/musondaAlexander/mabat/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/musondaAlexander/mabat/releases/tag/v0.1.0
