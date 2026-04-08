"""
Stub tests for config module.
"""

import json

from neurocad.config.config import load, save, save_api_key
from neurocad.config.defaults import DEFAULTS


def test_load_returns_dict():
    cfg = load()
    assert isinstance(cfg, dict)
    # Should contain default keys
    expected_keys = {"provider", "model", "base_url", "max_tokens", "temperature"}
    assert expected_keys.issubset(cfg.keys())
    # api_key should not be present
    assert "api_key" not in cfg


def test_save_does_not_crash():
    # Should not raise an exception
    cfg = load()
    save(cfg)


def test_save_api_key_no_exception():
    # Should not raise (keyring may be missing, but that's okay)
    save_api_key("dummy-key")


def test_load_merges_defaults_when_file_missing(monkeypatch, tmp_path):
    """If config file does not exist, load() should return defaults."""
    dummy_path = tmp_path / "nonexistent.json"
    monkeypatch.setattr("neurocad.config.config.CONFIG_PATH", dummy_path)
    # Ensure file does not exist
    assert not dummy_path.exists()
    cfg = load()
    # Should match DEFAULTS (except api_key which is stripped)
    expected = DEFAULTS.copy()
    expected.pop("api_key", None)
    assert cfg == expected


def test_load_ignores_unknown_keys(monkeypatch, tmp_path):
    """Unknown keys in config file should be ignored."""
    config_file = tmp_path / "config.json"
    # Write a config with extra unknown keys
    data = {"provider": "openai", "unknown_key": "should_be_ignored", "extra": 123}
    config_file.write_text(json.dumps(data))
    monkeypatch.setattr("neurocad.config.config.CONFIG_PATH", config_file)
    cfg = load()
    # Should contain only known keys (provider) merged with defaults
    assert "provider" in cfg
    assert cfg["provider"] == "openai"
    assert "unknown_key" not in cfg
    assert "extra" not in cfg
    # Defaults for other keys should be present
    assert "model" in cfg
    assert "max_tokens" in cfg


def test_load_strips_api_key_from_file(monkeypatch, tmp_path):
    """If config file contains api_key, it must be stripped from the result."""
    config_file = tmp_path / "config.json"
    data = {"provider": "openai", "api_key": "secret"}
    config_file.write_text(json.dumps(data))
    monkeypatch.setattr("neurocad.config.config.CONFIG_PATH", config_file)
    cfg = load()
    assert "api_key" not in cfg
    # Other keys should be present
    assert cfg["provider"] == "openai"


def test_save_does_not_write_api_key(monkeypatch, tmp_path):
    """save() should never write api_key to disk."""
    config_file = tmp_path / "config.json"
    monkeypatch.setattr("neurocad.config.config.CONFIG_PATH", config_file)
    cfg = DEFAULTS.copy()
    cfg["api_key"] = "super-secret"
    save(cfg)
    # Read raw file content
    raw = json.loads(config_file.read_text())
    assert "api_key" not in raw
    # Ensure other keys are present
    for key in DEFAULTS:
        if key != "api_key":
            assert key in raw
            assert raw[key] == DEFAULTS[key]
