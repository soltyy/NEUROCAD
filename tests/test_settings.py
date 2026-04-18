"""Tests for the Sprint 5.15 Settings dialog (tiered key storage + inline status)."""

from unittest.mock import MagicMock, patch

import pytest

from neurocad.ui.settings import SettingsDialog


def _mock_ui(dialog: SettingsDialog,
             provider: str = "openai",
             model: str = "gpt-4o",
             base_url: str = "",
             timeout: float = 180.0,
             max_objects: int = 1000,
             api_key: str = "",
             tier: str = "auto") -> None:
    """Replace dialog's UI widgets with MagicMocks set to the given values."""
    dialog._provider_combo = MagicMock()
    dialog._provider_combo.currentText.return_value = provider
    dialog._model_edit = MagicMock()
    dialog._model_edit.text.return_value = model
    dialog._base_url_edit = MagicMock()
    dialog._base_url_edit.text.return_value = base_url
    dialog._timeout_spin = MagicMock()
    dialog._timeout_spin.value.return_value = timeout
    dialog._max_objects_spin = MagicMock()
    dialog._max_objects_spin.value.return_value = max_objects
    dialog._api_key_edit = MagicMock()
    dialog._api_key_edit.text.return_value = api_key
    dialog._tier_auto = MagicMock()
    dialog._tier_plaintext = MagicMock()
    dialog._tier_session = MagicMock()
    dialog._tier_auto.isChecked.return_value = (tier == "auto")
    dialog._tier_plaintext.isChecked.return_value = (tier == "plaintext")
    dialog._tier_session.isChecked.return_value = (tier == "session")
    dialog._storage_status = MagicMock()


def test_settings_dialog_initialization(qapp):
    """SettingsDialog can be instantiated with default values and three radio buttons."""
    with patch("neurocad.ui.settings.load_config", return_value={"provider": "openai"}), \
         patch("neurocad.ui.settings.key_storage.load_key", return_value=(None, None)), \
         patch("neurocad.ui.settings.key_storage.available_backends", return_value=[]):
        dialog = SettingsDialog(None)
    # UI widgets exist
    assert dialog._provider_combo is not None
    assert dialog._model_edit is not None
    assert dialog._timeout_spin is not None
    assert dialog._api_key_edit is not None
    # Storage tier radio buttons
    assert dialog._tier_auto is not None
    assert dialog._tier_plaintext is not None
    assert dialog._tier_session is not None
    # Default tier is Automatic
    assert dialog._tier_auto.isChecked() is True
    assert dialog._tier_plaintext.isChecked() is False
    assert dialog._tier_session.isChecked() is False


def test_collect_config(qapp):
    """_collect_config returns config dict and api key string."""
    with patch("neurocad.ui.settings.load_config", return_value={"provider": "openai"}), \
         patch("neurocad.ui.settings.key_storage.load_key", return_value=(None, None)), \
         patch("neurocad.ui.settings.key_storage.available_backends", return_value=[]):
        dialog = SettingsDialog()
    _mock_ui(dialog, provider="anthropic", model="claude-3-5-sonnet",
             base_url="https://api.anthropic.com", timeout=180.0,
             max_objects=1000, api_key="secret-key")

    config, key = dialog._collect_config()
    assert config == {
        "provider": "anthropic",
        "model": "claude-3-5-sonnet",
        "base_url": "https://api.anthropic.com",
        "timeout": 180.0,
        "max_created_objects": 1000,
    }
    assert key == "secret-key"


def test_selected_tier_reports_auto_by_default(qapp):
    with patch("neurocad.ui.settings.load_config", return_value={"provider": "openai"}), \
         patch("neurocad.ui.settings.key_storage.load_key", return_value=(None, None)), \
         patch("neurocad.ui.settings.key_storage.available_backends", return_value=[]):
        dialog = SettingsDialog()
    _mock_ui(dialog, tier="auto")
    assert dialog._selected_tier() == "auto"


def test_selected_tier_plaintext(qapp):
    with patch("neurocad.ui.settings.load_config", return_value={"provider": "openai"}), \
         patch("neurocad.ui.settings.key_storage.load_key", return_value=(None, None)), \
         patch("neurocad.ui.settings.key_storage.available_backends", return_value=[]):
        dialog = SettingsDialog()
    _mock_ui(dialog, tier="plaintext")
    assert dialog._selected_tier() == "plaintext"


def test_selected_tier_session(qapp):
    with patch("neurocad.ui.settings.load_config", return_value={"provider": "openai"}), \
         patch("neurocad.ui.settings.key_storage.load_key", return_value=(None, None)), \
         patch("neurocad.ui.settings.key_storage.available_backends", return_value=[]):
        dialog = SettingsDialog()
    _mock_ui(dialog, tier="session")
    assert dialog._selected_tier() == "session"


def test_on_save_automatic_tier_persists_via_key_storage(qapp):
    """_on_save with Automatic tier calls save_api_key and shows inline status."""
    with patch("neurocad.ui.settings.load_config", return_value={"provider": "openai"}), \
         patch("neurocad.ui.settings.key_storage.load_key", return_value=(None, None)), \
         patch("neurocad.ui.settings.key_storage.available_backends", return_value=[]):
        dialog = SettingsDialog()
    _mock_ui(dialog, api_key="sk-test", tier="auto")

    with patch("neurocad.ui.settings.save_config") as mock_save_cfg, \
         patch("neurocad.ui.settings.save_api_key",
               return_value=("System keyring", None)) as mock_save_key, \
         patch.object(dialog, "accept") as mock_accept:
        dialog._on_save()

    # Config was saved (without api_key)
    mock_save_cfg.assert_called_once_with({
        "provider": "openai",
        "model": "gpt-4o",
        "timeout": 180.0,
        "max_created_objects": 1000,
    })
    # save_api_key was called with the chosen tier
    mock_save_key.assert_called_once_with("openai", "sk-test", tier="auto")
    # Dialog accepted, no MessageBox raised
    mock_accept.assert_called_once()
    # Inline status reflects the backend name
    assert dialog._storage_status.setText.called
    status_html = dialog._storage_status.setText.call_args.args[0]
    assert "System keyring" in status_html


def test_on_save_plaintext_tier_forces_plaintext(qapp):
    with patch("neurocad.ui.settings.load_config", return_value={"provider": "openai"}), \
         patch("neurocad.ui.settings.key_storage.load_key", return_value=(None, None)), \
         patch("neurocad.ui.settings.key_storage.available_backends", return_value=[]):
        dialog = SettingsDialog()
    _mock_ui(dialog, api_key="sk-plain", tier="plaintext")

    with patch("neurocad.ui.settings.save_config"), \
         patch("neurocad.ui.settings.save_api_key",
               return_value=("Plaintext file (owner-only)", None)) as mock_save_key, \
         patch.object(dialog, "accept"):
        dialog._on_save()

    mock_save_key.assert_called_once_with("openai", "sk-plain", tier="plaintext")
    status_html = dialog._storage_status.setText.call_args.args[0]
    assert "Plaintext" in status_html


def test_on_save_session_tier_does_not_call_save_api_key(qapp):
    """Session tier: build adapter, never call save_api_key."""
    with patch("neurocad.ui.settings.load_config", return_value={"provider": "openai"}), \
         patch("neurocad.ui.settings.key_storage.load_key", return_value=(None, None)), \
         patch("neurocad.ui.settings.key_storage.available_backends", return_value=[]):
        dialog = SettingsDialog()
    _mock_ui(dialog, api_key="sk-session", tier="session")

    with patch("neurocad.ui.settings.save_config"), \
         patch("neurocad.ui.settings.save_api_key") as mock_save_key, \
         patch("neurocad.ui.settings.load_adapter_with_session_key",
               return_value="fake-adapter") as mock_load, \
         patch.object(dialog, "accept"):
        dialog._on_save()

    mock_save_key.assert_not_called()
    mock_load.assert_called_once()
    assert dialog._adapter == "fake-adapter"


def test_on_save_missing_key_shows_inline_warning(qapp):
    """Empty key field → inline warning, no modal."""
    with patch("neurocad.ui.settings.load_config", return_value={"provider": "openai"}), \
         patch("neurocad.ui.settings.key_storage.load_key", return_value=(None, None)), \
         patch("neurocad.ui.settings.key_storage.available_backends", return_value=[]):
        dialog = SettingsDialog()
    _mock_ui(dialog, api_key="")

    with patch("neurocad.ui.settings.save_config") as mock_save_cfg, \
         patch("neurocad.ui.settings.save_api_key") as mock_save_key:
        dialog._on_save()

    # Nothing was saved
    mock_save_cfg.assert_not_called()
    mock_save_key.assert_not_called()
    # Inline warning shown
    dialog._storage_status.setText.assert_called()
    assert "API key" in dialog._storage_status.setText.call_args.args[0]


def test_on_save_reports_error_inline_when_all_backends_fail(qapp):
    with patch("neurocad.ui.settings.load_config", return_value={"provider": "openai"}), \
         patch("neurocad.ui.settings.key_storage.load_key", return_value=(None, None)), \
         patch("neurocad.ui.settings.key_storage.available_backends", return_value=[]):
        dialog = SettingsDialog()
    _mock_ui(dialog, api_key="sk-x")

    with patch("neurocad.ui.settings.save_config"), \
         patch("neurocad.ui.settings.save_api_key",
               return_value=("none", "every backend failed")), \
         patch.object(dialog, "accept") as mock_accept:
        dialog._on_save()

    mock_accept.assert_not_called()
    status_html = dialog._storage_status.setText.call_args.args[0]
    assert "Could not persist" in status_html or "backend failed" in status_html


def test_on_use_once(qapp):
    """_on_use_once creates adapter and stores it; no modal."""
    with patch("neurocad.ui.settings.load_config", return_value={"provider": "openai"}), \
         patch("neurocad.ui.settings.key_storage.load_key", return_value=(None, None)), \
         patch("neurocad.ui.settings.key_storage.available_backends", return_value=[]):
        dialog = SettingsDialog()
    _mock_ui(dialog, api_key="session-key")

    mock_adapter = MagicMock()
    with patch("neurocad.ui.settings.load_adapter_with_session_key",
               return_value=mock_adapter) as mock_load, \
         patch.object(dialog, "accept") as mock_accept:
        dialog._on_use_once()

    mock_load.assert_called_once()
    assert dialog._adapter is mock_adapter
    mock_accept.assert_called_once()


def test_load_current_shows_existing_backend(qapp):
    """If a key is stored, _load_current displays the backend's name in the status line."""
    with patch("neurocad.ui.settings.load_config", return_value={"provider": "openai"}), \
         patch("neurocad.ui.settings.key_storage.load_key",
               return_value=("sk-stored", "macOS Keychain")), \
         patch("neurocad.ui.settings.key_storage.available_backends", return_value=[]):
        dialog = SettingsDialog()
    # After __init__, _load_current has already been called; check status has been set
    # by re-running with mocked widgets.
    _mock_ui(dialog, provider="openai")
    with patch("neurocad.ui.settings.key_storage.load_key",
               return_value=("sk-stored", "macOS Keychain")):
        dialog._load_current()
    status_html = dialog._storage_status.setText.call_args.args[0]
    assert "macOS Keychain" in status_html


def test_session_key_not_persisted(qapp):
    """Using the session tier does not call save_api_key at all."""
    with patch("neurocad.ui.settings.load_config", return_value={"provider": "openai"}), \
         patch("neurocad.ui.settings.key_storage.load_key", return_value=(None, None)), \
         patch("neurocad.ui.settings.key_storage.available_backends", return_value=[]):
        dialog = SettingsDialog()
    _mock_ui(dialog, api_key="sk-session", tier="session")

    with patch("neurocad.ui.settings.save_api_key") as mock_save_key, \
         patch("neurocad.ui.settings.save_config"), \
         patch("neurocad.ui.settings.load_adapter_with_session_key",
               return_value=MagicMock()), \
         patch.object(dialog, "accept"):
        dialog._on_save()
        dialog._on_use_once()

    mock_save_key.assert_not_called()


def test_settings_max_created_objects_default(qapp):
    """Config without max_created_objects falls back to 1000 in the UI."""
    with patch("neurocad.ui.settings.load_config", return_value={"provider": "openai"}), \
         patch("neurocad.ui.settings.key_storage.load_key", return_value=(None, None)), \
         patch("neurocad.ui.settings.key_storage.available_backends", return_value=[]):
        dialog = SettingsDialog()
    _mock_ui(dialog)
    dialog._config = {"provider": "openai"}  # no max_created_objects
    dialog._load_current()
    dialog._max_objects_spin.setValue.assert_called_with(1000)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
