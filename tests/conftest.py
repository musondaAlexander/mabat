"""Shared fixtures."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

from mabat._shared import config

# Rich reads FORCE_COLOR/NO_COLOR when a Console is created (at import of mabat.cli).
# Keep CLI output plain and deterministic whatever the developer's shell exports.
for _name in ("FORCE_COLOR", "CLICOLOR_FORCE", "TTY_COMPATIBLE"):
    os.environ.pop(_name, None)
os.environ["NO_COLOR"] = "1"


@pytest.fixture(autouse=True)
def _fresh_settings(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[None]:
    """Isolate every test from a developer's local ``mabat.toml`` and ``$MABAT_CONFIG``,
    and make sampling non-blocking so the suite stays fast."""
    monkeypatch.delenv(config.ENV_CONFIG_PATH, raising=False)
    cwd = tmp_path_factory.mktemp("cwd")
    (cwd / config.LOCAL_CONFIG_NAME).write_text(
        "[sampling]\ncpu_sample_seconds = 0.0\n"
        "[processes]\nsample_seconds = 0.0\ntop_n = 0\n"  # no per-process scan (slow hosts)
    )
    monkeypatch.chdir(cwd)
    config.settings.cache_clear()
    yield
    config.settings.cache_clear()
