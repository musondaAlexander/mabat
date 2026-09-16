"""Shared fixtures."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from mabat._shared import config


@pytest.fixture(autouse=True)
def _fresh_settings(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[None]:
    """Isolate every test from a developer's local ``mabat.toml`` and ``$MABAT_CONFIG``."""
    monkeypatch.delenv(config.ENV_CONFIG_PATH, raising=False)
    monkeypatch.chdir(tmp_path_factory.mktemp("cwd"))
    config.settings.cache_clear()
    yield
    config.settings.cache_clear()
