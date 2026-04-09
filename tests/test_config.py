"""Test configuration management."""

import json
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

from neurocad.config.config import load, save, save_api_key


def test_get_config_dir_freecad():
    """Prefer FreeCAD.ConfigGet("UserAppData")."""
    mock_freecad = MagicMock()
    mock_freecad.ConfigGet.return_value = "/fake/path"
    with patch.dict("sys.modules", {"FreeCAD": mock_freecad}):
        # Re‑import to pick up the mock
        import importlib

        import neurocad.config.config
        importlib.reload(neurocad.config.config)
        result = neurocad.config.config._get_config_dir()
        assert result == Path("/fake/path") / "neurocad"


def test_get_config_dir_xdg():
    """Fallback to XDG ~/.config/FreeCAD."""
    with (
        patch.dict("sys.modules", {"FreeCAD": None}),
        patch.object(Path, "exists", side_effect=lambda *args: True),
    ):
        import importlib

        import neurocad.config.config
        importlib.reload(neurocad.config.config)
        result = neurocad.config.config._get_config_dir()
        expected = Path.home() / ".config" / "FreeCAD" / "neurocad"
        assert result == expected


def test_get_config_dir_legacy():
    """Final fallback to ~/.freecad/neurocad."""
    with (
        patch.dict("sys.modules", {"FreeCAD": None}),
        patch.object(Path, "exists", side_effect=lambda *args: False),
    ):
        import importlib

        import neurocad.config.config
        importlib.reload(neurocad.config.config)
        result = neurocad.config.config._get_config_dir()
        expected = Path.home() / ".freecad" / "neurocad"
        assert result == expected


def test_load_missing_file():
    """If config.json doesn't exist, return defaults."""
    with patch.object(Path, "exists", return_value=False):
        config = load()
    assert config["provider"] == "openai"
    assert config["model"] == "gpt-4o-mini"


def test_load_existing_file():
    """Existing config should be loaded and merged with defaults."""
    mock_data = {"provider": "anthropic", "model": "claude-3-haiku"}
    with (
        patch.object(Path, "exists", return_value=True),
        patch("builtins.open", mock_open(read_data=json.dumps(mock_data))),
    ):
        config = load()
    assert config["provider"] == "anthropic"
    assert config["model"] == "claude-3-haiku"


def test_save_omits_api_key():
    """save() should never write api_key to disk."""
    config = {"provider": "openai", "api_key": "sk-secret", "model": "gpt-4"}
    mock_file = mock_open()
    with patch.object(Path, "mkdir"), patch("builtins.open", mock_file):
        save(config)
    # Verify the written JSON does not contain api_key
    written = "".join(call.args[0] for call in mock_file().write.call_args_list)
    parsed = json.loads(written)
    assert "api_key" not in parsed
    assert parsed["provider"] == "openai"
    assert parsed["model"] == "gpt-4"


def test_save_api_key_calls_keyring():
    """save_api_key should store the key via keyring."""
    mock_keyring = MagicMock()
    with patch("neurocad.config.config.keyring", mock_keyring):
        save_api_key("openai", "sk-test")
    mock_keyring.set_password.assert_called_once_with("neurocad", "openai", "sk-test")


def test_save_api_key_without_keyring_raises_runtime_error():
    """save_api_key should fail clearly when keyring is unavailable."""
    with patch("neurocad.config.config.keyring", None):
        try:
            save_api_key("openai", "sk-test")
        except RuntimeError as exc:
            assert "keyring is not installed" in str(exc)
        else:
            raise AssertionError("save_api_key() should raise when keyring is unavailable")
