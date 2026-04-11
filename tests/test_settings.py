"""Tests for settings dialog and adapter refresh."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from neurocad.ui.settings import SettingsDialog


def test_settings_dialog_initialization(qapp):
    """SettingsDialog can be instantiated with default values."""
    # No parent widget (None)
    parent = None
    # Ensure keyring import works
    with patch.dict(sys.modules, {"keyring": MagicMock()}), \
         patch("neurocad.ui.settings.load_config", return_value={"provider": "openai"}):
        dialog = SettingsDialog(parent)
        assert dialog.parent() is parent
        # UI elements exist
        assert dialog._provider_combo is not None
        assert dialog._model_edit is not None
        assert dialog._base_url_edit is not None
        assert dialog._timeout_spin is not None
        assert dialog._api_key_edit is not None
        # Provider combo is populated
        assert dialog._provider_combo.count() > 0


def test_collect_config():
    """_collect_config returns config dict and api key string."""
    dialog = SettingsDialog()
    # Mock UI elements
    dialog._provider_combo = MagicMock()
    dialog._provider_combo.currentText.return_value = "anthropic"
    dialog._model_edit = MagicMock()
    dialog._model_edit.text.return_value = "claude-3-5-sonnet"
    dialog._base_url_edit = MagicMock()
    dialog._base_url_edit.text.return_value = "https://api.anthropic.com"
    dialog._timeout_spin = MagicMock()
    dialog._timeout_spin.value.return_value = 120.0
    dialog._max_objects_spin = MagicMock()
    dialog._max_objects_spin.value.return_value = 1000
    dialog._api_key_edit = MagicMock()
    dialog._api_key_edit.text.return_value = "secret-key"

    config, key = dialog._collect_config()
    assert config == {
        "provider": "anthropic",
        "model": "claude-3-5-sonnet",
        "base_url": "https://api.anthropic.com",
        "timeout": 120.0,
        "max_created_objects": 1000,
    }
    assert key == "secret-key"

    # Empty fields are omitted
    dialog._model_edit.text.return_value = ""
    dialog._base_url_edit.text.return_value = ""
    config, key = dialog._collect_config()
    assert "model" not in config
    assert "base_url" not in config
    # max_created_objects still present (has default)
    assert config["max_created_objects"] == 1000
    assert config["provider"] == "anthropic"
    assert config["timeout"] == 120.0


def test_on_save_with_keyring(qapp):
    """_on_save writes config and API key to keyring."""
    dialog = SettingsDialog()
    # Simulate keyring available
    dialog._keyring_available = True
    # Mock UI
    dialog._provider_combo = MagicMock()
    dialog._provider_combo.currentText.return_value = "openai"
    dialog._model_edit = MagicMock()
    dialog._model_edit.text.return_value = "gpt-4o"
    dialog._base_url_edit = MagicMock()
    dialog._base_url_edit.text.return_value = ""
    dialog._timeout_spin = MagicMock()
    dialog._timeout_spin.value.return_value = 120.0
    dialog._max_objects_spin = MagicMock()
    dialog._max_objects_spin.value.return_value = 1000
    dialog._api_key_edit = MagicMock()
    dialog._api_key_edit.text.return_value = "key123"

    # Mock config.save and config.save_api_key
    with patch("neurocad.ui.settings.save_config") as mock_save, \
         patch("neurocad.ui.settings.save_api_key") as mock_save_key, \
         patch("neurocad.ui.settings.QtWidgets.QMessageBox.information") as mock_msg:
        # Call
        dialog._on_save()
        # Verify config saved (without api_key)
        mock_save.assert_called_once_with({
            "provider": "openai",
            "model": "gpt-4o",
            "timeout": 120.0,
            "max_created_objects": 1000,
        })
        # Verify API key saved
        mock_save_key.assert_called_once_with("openai", "key123")
        # Verify success message shown
        mock_msg.assert_called_once()


def test_on_save_without_keyring(qapp):
    """_on_save shows error when keyring is missing."""
    dialog = SettingsDialog()
    dialog._keyring_available = False
    dialog._provider_combo = MagicMock()
    dialog._provider_combo.currentText.return_value = "openai"
    dialog._model_edit = MagicMock()
    dialog._model_edit.text.return_value = ""
    dialog._base_url_edit = MagicMock()
    dialog._base_url_edit.text.return_value = ""
    dialog._timeout_spin = MagicMock()
    dialog._timeout_spin.value.return_value = 120.0
    dialog._max_objects_spin = MagicMock()
    dialog._max_objects_spin.value.return_value = 1000
    dialog._api_key_edit = MagicMock()
    dialog._api_key_edit.text.return_value = "key123"

    # Simulate missing keyring (save_api_key raises RuntimeError)
    with patch("neurocad.ui.settings.save_config") as mock_save, \
         patch(
             "neurocad.ui.settings.save_api_key",
             side_effect=RuntimeError("keyring missing")
         ), \
         patch("neurocad.ui.settings.QtWidgets.QMessageBox.warning") as mock_warning:
        dialog._on_save()
        # Config still saved
        mock_save.assert_called_once_with(
            {"provider": "openai", "timeout": 120.0, "max_created_objects": 1000}
        )
        # Warning message shown
        mock_warning.assert_called_once()


def test_on_use_once(qapp):
    """_on_use_once creates adapter with session key and emits accepted."""
    dialog = SettingsDialog()
    dialog._provider_combo = MagicMock()
    dialog._provider_combo.currentText.return_value = "openai"
    dialog._model_edit = MagicMock()
    dialog._model_edit.text.return_value = "gpt-4o"
    dialog._base_url_edit = MagicMock()
    dialog._base_url_edit.text.return_value = ""
    dialog._timeout_spin = MagicMock()
    dialog._timeout_spin.value.return_value = 120.0
    dialog._max_objects_spin = MagicMock()
    dialog._max_objects_spin.value.return_value = 1000
    dialog._api_key_edit = MagicMock()
    dialog._api_key_edit.text.return_value = "session-key"

    mock_adapter = MagicMock()
    with patch(
        "neurocad.ui.settings.load_adapter_with_session_key",
        return_value=mock_adapter,
    ) as mock_load, \
         patch("neurocad.ui.settings.QtWidgets.QMessageBox.information") as mock_info, \
         patch.object(dialog, "accept") as mock_accept:
        dialog._on_use_once()
        # Should call load_adapter_with_session_key with config and key
        mock_load.assert_called_once_with(
            {
                "provider": "openai",
                "model": "gpt-4o",
                "timeout": 120.0,
                "max_created_objects": 1000,
            },
            "session-key"
        )
        # Adapter stored
        assert dialog._adapter is mock_adapter
        # Success message shown
        mock_info.assert_called_once()
        # Dialog accepted
        mock_accept.assert_called_once()


def test_load_current(qapp):
    """_load_current populates UI from config."""
    dialog = SettingsDialog()
    dialog._provider_combo = MagicMock()
    dialog._model_edit = MagicMock()
    dialog._base_url_edit = MagicMock()
    dialog._timeout_spin = MagicMock()
    dialog._api_key_edit = MagicMock()
    dialog._config = {
        "provider": "anthropic",
        "model": "claude-3-5-sonnet",
        "base_url": "https://api.anthropic.com",
        "timeout": 120.0,
    }

    dialog._load_current()
    # Provider combo set
    dialog._provider_combo.setCurrentText.assert_called_once_with("anthropic")
    # Model line edit set
    dialog._model_edit.setText.assert_called_once_with("claude-3-5-sonnet")
    # Base URL line edit set
    dialog._base_url_edit.setText.assert_called_once_with("https://api.anthropic.com")
    dialog._timeout_spin.setValue.assert_called_once_with(120.0)
    # API key line edit cleared
    dialog._api_key_edit.clear.assert_called_once_with()


def test_load_current_no_keyring(qapp):
    """_load_current handles missing keyring gracefully (no placeholder)."""
    dialog = SettingsDialog()
    dialog._provider_combo = MagicMock()
    dialog._model_edit = MagicMock()
    dialog._base_url_edit = MagicMock()
    dialog._timeout_spin = MagicMock()
    dialog._api_key_edit = MagicMock()
    dialog._config = {"provider": "openai"}

    dialog._load_current()
    # API key line edit cleared (no placeholder set)
    dialog._timeout_spin.setValue.assert_called_once_with(120.0)
    dialog._api_key_edit.clear.assert_called_once_with()


def test_settings_max_created_objects(qapp):
    """SettingsDialog loads and saves max_created_objects."""
    dialog = SettingsDialog()
    # Mock UI elements
    dialog._provider_combo = MagicMock()
    dialog._model_edit = MagicMock()
    dialog._base_url_edit = MagicMock()
    dialog._timeout_spin = MagicMock()
    dialog._api_key_edit = MagicMock()
    dialog._max_objects_spin = MagicMock()
    # Simulate config with custom limit
    dialog._config = {
        "provider": "openai",
        "model": "gpt-4",
        "timeout": 60.0,
        "max_created_objects": 500,
    }

    # Test _load_current
    dialog._load_current()
    dialog._max_objects_spin.setValue.assert_called_once_with(500)
    dialog._timeout_spin.setValue.assert_called_once_with(60.0)

    # Reset mocks for _collect_config test
    dialog._provider_combo.currentText.return_value = "openai"
    dialog._model_edit.text.return_value = "gpt-4"
    dialog._base_url_edit.text.return_value = ""
    dialog._timeout_spin.value.return_value = 60.0
    dialog._max_objects_spin.value.return_value = 500
    dialog._api_key_edit.text.return_value = ""

    config, key = dialog._collect_config()
    assert config["max_created_objects"] == 500
    assert config["provider"] == "openai"
    assert config["timeout"] == 60.0
    assert key == ""


def test_settings_max_created_objects_default(qapp):
    """SettingsDialog uses default 1000 when config missing max_created_objects."""
    dialog = SettingsDialog()
    dialog._provider_combo = MagicMock()
    dialog._model_edit = MagicMock()
    dialog._base_url_edit = MagicMock()
    dialog._timeout_spin = MagicMock()
    dialog._api_key_edit = MagicMock()
    dialog._max_objects_spin = MagicMock()
    dialog._config = {"provider": "openai"}  # no max_created_objects

    dialog._load_current()
    # Should default to 1000
    dialog._max_objects_spin.setValue.assert_called_once_with(1000)

    # Reset mocks
    dialog._provider_combo.currentText.return_value = "openai"
    dialog._model_edit.text.return_value = ""
    dialog._base_url_edit.text.return_value = ""
    dialog._timeout_spin.value.return_value = 120.0
    dialog._max_objects_spin.value.return_value = 1000
    dialog._api_key_edit.text.return_value = ""

    config, key = dialog._collect_config()
    assert config["max_created_objects"] == 1000
    assert config["timeout"] == 120.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
