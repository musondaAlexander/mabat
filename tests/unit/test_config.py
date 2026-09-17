from __future__ import annotations

from pathlib import Path

import pytest

from mabat._shared import config


def test_defaults_load_and_are_sane() -> None:
    s = config.load_settings()
    assert s.cpu_sample_seconds >= 0
    assert s.top_processes >= 0  # conftest pins top_n = 0 for speed
    assert s.process_sample_seconds >= 0
    assert s.thresholds.warn_percent <= s.thresholds.critical_percent
    assert isinstance(s.hidden_interface_patterns, tuple)


def test_local_file_overrides_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / config.LOCAL_CONFIG_NAME).write_text("[processes]\ntop_n = 3\n")
    assert config.load_settings().top_processes == 3


def test_env_path_overrides_local_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / config.LOCAL_CONFIG_NAME).write_text("[processes]\ntop_n = 3\n")
    env_file = tmp_path / "env.toml"
    env_file.write_text("[processes]\ntop_n = 4\n")
    monkeypatch.setenv(config.ENV_CONFIG_PATH, str(env_file))
    assert config.load_settings().top_processes == 4


def test_explicit_path_wins_and_must_exist(tmp_path: Path) -> None:
    explicit = tmp_path / "explicit.toml"
    explicit.write_text("[thresholds]\nwarn_percent = 50\ncritical_percent = 60\n")
    s = config.load_settings(explicit)
    assert (s.thresholds.warn_percent, s.thresholds.critical_percent) == (50.0, 60.0)
    with pytest.raises(config.SettingsError, match="not found"):
        config.load_settings(tmp_path / "missing.toml")


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("[processes]\ntop_n = 'ten'\n", "wrong type"),
        ("[processes]\ntop_n = true\n", "wrong type"),
        ("[processes]\nmax = 3\n", "unknown setting"),
        ("[nope]\nx = 1\n", "unknown setting"),
        ("processes = 3\n", "must be a table"),
        ("[processes\n", "invalid TOML"),
        ("[thresholds]\nwarn_percent = 99\ncritical_percent = 50\n", "must not exceed"),
        ("[processes]\ntop_n = -1\n", "not be negative"),
        ("[processes]\nsample_seconds = -0.5\n", "not be negative"),
        ("[network]\nprobe_address = 'dns.google'\n", "IPv4 or IPv6 address"),
    ],
)
def test_invalid_settings_are_rejected_at_the_boundary(
    tmp_path: Path, text: str, message: str
) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text(text)
    with pytest.raises(config.SettingsError, match=message):
        config.load_settings(bad)


def test_settings_is_cached_until_cleared(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    first = config.settings()
    monkeypatch.chdir(tmp_path)
    (tmp_path / config.LOCAL_CONFIG_NAME).write_text("[processes]\ntop_n = 1\n")
    assert config.settings() is first
    config.settings.cache_clear()
    assert config.settings().top_processes == 1


def test_boolean_settings_accept_only_booleans(tmp_path: Path) -> None:
    good = tmp_path / "good.toml"
    good.write_text("[gpu]\ncounters = true\n")
    assert config.load_settings(good).gpu_counters is True
    bad = tmp_path / "bad.toml"
    bad.write_text("[gpu]\ncounters = 1\n")
    with pytest.raises(config.SettingsError, match="true or false"):
        config.load_settings(bad)
