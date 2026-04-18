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
    assert config["timeout"] == 180.0


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
    assert config["timeout"] == 180.0


def test_save_omits_api_key():
    """save() should never write api_key to disk."""
    config = {"provider": "openai", "api_key": "sk-secret", "model": "gpt-4", "timeout": 180.0}
    mock_file = mock_open()
    with patch.object(Path, "mkdir"), patch("builtins.open", mock_file):
        save(config)
    # Verify the written JSON does not contain api_key
    written = "".join(call.args[0] for call in mock_file().write.call_args_list)
    parsed = json.loads(written)
    assert "api_key" not in parsed
    assert parsed["provider"] == "openai"
    assert parsed["model"] == "gpt-4"
    assert parsed["timeout"] == 180.0


def test_save_api_key_delegates_to_key_storage():
    """Sprint 5.15: save_api_key delegates to key_storage.save_key and returns
    the (backend_name, error) tuple, never raises.
    """
    with patch("neurocad.config.config.key_storage.save_key",
               return_value=("System keyring", None)) as mock_save:
        result = save_api_key("openai", "sk-test")
    mock_save.assert_called_once()
    # Default tier is Automatic
    kwargs = mock_save.call_args.kwargs
    assert kwargs.get("tier") == "auto" or "auto" in str(mock_save.call_args)
    assert result == ("System keyring", None)


def test_save_api_key_never_raises_when_all_backends_fail():
    """Sprint 5.15: previously raised RuntimeError when keyring missing.
    Now it returns (backend_name, error_str) and the UI shows it inline.
    """
    with patch("neurocad.config.config.key_storage.save_key",
               return_value=("none", "every backend failed")):
        name, err = save_api_key("openai", "sk-test")
    assert name == "none"
    assert "every backend" in err


def test_load_includes_max_created_objects():
    """load() should include max_created_objects with default 1000."""
    with patch.object(Path, "exists", return_value=False):
        config = load()
    assert config["max_created_objects"] == 1000


def test_save_includes_max_created_objects():
    """save() should write max_created_objects."""
    config = {"provider": "openai", "model": "gpt-4", "timeout": 180.0, "max_created_objects": 500}
    mock_file = mock_open()
    with patch.object(Path, "mkdir"), patch("builtins.open", mock_file):
        save(config)
    written = "".join(call.args[0] for call in mock_file().write.call_args_list)
    parsed = json.loads(written)
    assert parsed["max_created_objects"] == 500
    assert parsed["provider"] == "openai"


def test_load_includes_exec_handoff_timeout():
    """Sprint 5.6: load() exposes exec_handoff_timeout_s with default 60.0."""
    with patch.object(Path, "exists", return_value=False):
        config = load()
    assert config["exec_handoff_timeout_s"] == 60.0
