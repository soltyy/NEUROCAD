"""Tests for the Sprint 5.17 Settings dialog.

Single Model dropdown (populated from `neurocad.llm.models.MODELS`) replaces
the old provider/model/base-URL triple. API-key tier radios (Automatic /
Plaintext file / Session only) from Sprint 5.15 are preserved.
"""

from unittest.mock import MagicMock, patch

import pytest

from neurocad.ui.settings import SettingsDialog


def _mock_ui(dialog: SettingsDialog,
             model_id: str = "openai:gpt-4o-mini",
             timeout: float = 180.0,
             max_objects: int = 1000,
             api_key: str = "",
             tier: str = "auto") -> None:
    """Replace the dialog's real widgets with MagicMocks."""
    dialog._model_combo = MagicMock()
    dialog._model_combo.currentData.return_value = model_id
    dialog._model_info = MagicMock()
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
    """Sprint 5.17: dialog has a model combo + 3 tier radios; no provider/base_url widgets."""
    with patch("neurocad.ui.settings.load_config",
               return_value={"model_id": "openai:gpt-4o-mini"}), \
         patch("neurocad.ui.settings.key_storage.load_key", return_value=(None, None)), \
         patch("neurocad.ui.settings.key_storage.available_backends", return_value=[]):
        dialog = SettingsDialog(None)

    assert dialog._model_combo is not None
    # Verify the combo contains all registry models
    from neurocad.llm import models as reg
    assert dialog._model_combo.count() == len(reg.list_models())
    # Old widgets are gone
    assert not hasattr(dialog, "_provider_combo")
    assert not hasattr(dialog, "_base_url_edit")
    assert not hasattr(dialog, "_model_edit")
    # Tier radios
    assert dialog._tier_auto is not None
    assert dialog._tier_auto.isChecked() is True


def test_collect_config_returns_model_id_and_spec(qapp):
    """Sprint 5.17: _collect_config returns (config, api_key, spec)."""
    with patch("neurocad.ui.settings.load_config",
               return_value={"model_id": "openai:gpt-4o-mini"}), \
         patch("neurocad.ui.settings.key_storage.load_key", return_value=(None, None)), \
         patch("neurocad.ui.settings.key_storage.available_backends", return_value=[]):
        dialog = SettingsDialog()
    _mock_ui(dialog, model_id="deepseek:chat", api_key="sk-ds", timeout=120.0, max_objects=500)

    config, key, spec = dialog._collect_config()
    assert config["model_id"] == "deepseek:chat"
    assert config["timeout"] == 120.0
    assert config["max_created_objects"] == 500
    # Legacy fields are NOT in the new config
    assert "provider" not in config
    assert "base_url" not in config
    assert key == "sk-ds"
    assert spec is not None
    assert spec.id == "deepseek:chat"
    assert spec.key_slug == "deepseek"
    assert spec.base_url == "https://api.deepseek.com/v1"


def test_on_save_persists_key_under_spec_key_slug(qapp):
    """Sprint 5.17: API key is saved under spec.key_slug, NOT the adapter class name."""
    with patch("neurocad.ui.settings.load_config",
               return_value={"model_id": "openai:gpt-4o-mini"}), \
         patch("neurocad.ui.settings.key_storage.load_key", return_value=(None, None)), \
         patch("neurocad.ui.settings.key_storage.available_backends", return_value=[]):
        dialog = SettingsDialog()
    # DeepSeek uses openai adapter but must store key under "deepseek".
    _mock_ui(dialog, model_id="deepseek:chat", api_key="sk-deepseek", tier="auto")

    with patch("neurocad.ui.settings.save_config") as mock_save_cfg, \
         patch("neurocad.ui.settings.save_api_key",
               return_value=("macOS Keychain", None)) as mock_save_key, \
         patch.object(dialog, "accept") as mock_accept:
        dialog._on_save()

    mock_save_cfg.assert_called_once()
    saved = mock_save_cfg.call_args.args[0]
    assert saved["model_id"] == "deepseek:chat"
    # Key saved under "deepseek", not "openai"!
    mock_save_key.assert_called_once_with("deepseek", "sk-deepseek", tier="auto")
    mock_accept.assert_called_once()


def test_on_save_openai_uses_openai_key_slug(qapp):
    """OpenAI models store the key under 'openai' slug."""
    with patch("neurocad.ui.settings.load_config",
               return_value={"model_id": "openai:gpt-4o"}), \
         patch("neurocad.ui.settings.key_storage.load_key", return_value=(None, None)), \
         patch("neurocad.ui.settings.key_storage.available_backends", return_value=[]):
        dialog = SettingsDialog()
    _mock_ui(dialog, model_id="openai:gpt-4o", api_key="sk-openai", tier="auto")

    with patch("neurocad.ui.settings.save_config"), \
         patch("neurocad.ui.settings.save_api_key",
               return_value=("System keyring", None)) as mock_save_key, \
         patch.object(dialog, "accept"):
        dialog._on_save()

    mock_save_key.assert_called_once_with("openai", "sk-openai", tier="auto")


def test_on_save_session_tier_builds_adapter_and_skips_storage(qapp):
    with patch("neurocad.ui.settings.load_config",
               return_value={"model_id": "openai:gpt-4o-mini"}), \
         patch("neurocad.ui.settings.key_storage.load_key", return_value=(None, None)), \
         patch("neurocad.ui.settings.key_storage.available_backends", return_value=[]):
        dialog = SettingsDialog()
    _mock_ui(dialog, model_id="openai:gpt-4o-mini", api_key="sk-session", tier="session")

    with patch("neurocad.ui.settings.save_config"), \
         patch("neurocad.ui.settings.save_api_key") as mock_save_key, \
         patch("neurocad.ui.settings.load_adapter_with_session_key",
               return_value="fake-adapter") as mock_load, \
         patch.object(dialog, "accept"):
        dialog._on_save()

    mock_save_key.assert_not_called()
    mock_load.assert_called_once()
    assert dialog._adapter == "fake-adapter"


def test_on_save_missing_key_with_no_stored_key_warns(qapp):
    """Empty key field AND no stored key → inline warning, no save."""
    with patch("neurocad.ui.settings.load_config",
               return_value={"model_id": "openai:gpt-4o-mini"}), \
         patch("neurocad.ui.settings.key_storage.load_key", return_value=(None, None)), \
         patch("neurocad.ui.settings.key_storage.available_backends", return_value=[]):
        dialog = SettingsDialog()
    _mock_ui(dialog, api_key="")

    # load_key MUST be patched during _on_save too (the dialog queries it to
    # decide whether to skip the "missing key" warning).
    with patch("neurocad.ui.settings.key_storage.load_key", return_value=(None, None)), \
         patch("neurocad.ui.settings.save_config") as mock_save_cfg, \
         patch("neurocad.ui.settings.save_api_key") as mock_save_key:
        dialog._on_save()

    mock_save_cfg.assert_not_called()
    mock_save_key.assert_not_called()
    dialog._storage_status.setText.assert_called()
    assert "API key" in dialog._storage_status.setText.call_args.args[0]


def test_on_save_empty_key_with_stored_key_saves_config_only(qapp):
    """Sprint 5.17: if an API key is already stored for this slug, an empty
    field should let the user update OTHER settings without re-entering the key.
    """
    with patch("neurocad.ui.settings.load_config",
               return_value={"model_id": "openai:gpt-4o-mini"}), \
         patch("neurocad.ui.settings.key_storage.load_key",
               return_value=("existing-key", "macOS Keychain")), \
         patch("neurocad.ui.settings.key_storage.available_backends", return_value=[]):
        dialog = SettingsDialog()
    _mock_ui(dialog, api_key="", tier="auto")

    with patch("neurocad.ui.settings.key_storage.load_key",
               return_value=("existing-key", "macOS Keychain")), \
         patch("neurocad.ui.settings.save_config") as mock_save_cfg, \
         patch("neurocad.ui.settings.save_api_key") as mock_save_key, \
         patch.object(dialog, "accept") as mock_accept:
        dialog._on_save()

    mock_save_cfg.assert_called_once()
    mock_save_key.assert_not_called()
    mock_accept.assert_called_once()


def test_on_use_once(qapp):
    with patch("neurocad.ui.settings.load_config",
               return_value={"model_id": "openai:gpt-4o-mini"}), \
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
    # Config passed to load_adapter_with_session_key has model_id, not legacy fields
    passed_config = mock_load.call_args.args[0]
    assert passed_config["model_id"] == "openai:gpt-4o-mini"
    assert dialog._adapter is mock_adapter
    mock_accept.assert_called_once()


def test_on_save_preserves_non_ui_config_fields(qapp):
    """Sprint 5.18: editing config in Settings must NOT wipe fields the dialog
    doesn't expose (audit_log_enabled, snapshot_max_chars, exec_handoff_timeout_s).
    Regression test for the "editing shouldn't spoil config" bug.
    """
    loaded_config = {
        "model_id": "deepseek:chat",
        "timeout": 360.0,
        "max_created_objects": 1000,
        "audit_log_enabled": False,          # ← user customized
        "snapshot_max_chars": 2000,          # ← user customized
        "exec_handoff_timeout_s": 120.0,     # ← user customized
    }

    with patch("neurocad.ui.settings.load_config", return_value=loaded_config), \
         patch("neurocad.ui.settings.key_storage.load_key", return_value=(None, None)), \
         patch("neurocad.ui.settings.key_storage.available_backends", return_value=[]):
        dialog = SettingsDialog()
    _mock_ui(dialog, model_id="deepseek:chat", api_key="sk-ds", tier="auto",
             timeout=360.0, max_objects=1000)
    # The dialog loaded the full config into self._config
    dialog._config = loaded_config

    with patch("neurocad.ui.settings.key_storage.load_key", return_value=(None, None)), \
         patch("neurocad.ui.settings.save_config") as mock_save, \
         patch("neurocad.ui.settings.save_api_key",
               return_value=("System keyring", None)), \
         patch.object(dialog, "accept"):
        dialog._on_save()

    # The saved config MUST include the user's customized non-UI fields.
    saved = mock_save.call_args.args[0]
    assert saved["audit_log_enabled"] is False, "audit_log_enabled wiped on save!"
    assert saved["snapshot_max_chars"] == 2000, "snapshot_max_chars wiped on save!"
    assert saved["exec_handoff_timeout_s"] == 120.0, "exec_handoff_timeout_s wiped on save!"
    # And the UI-editable fields use the values the dialog collected.
    assert saved["model_id"] == "deepseek:chat"
    assert saved["timeout"] == 360.0
    assert saved["max_created_objects"] == 1000


def test_on_save_drops_legacy_provider_and_base_url(qapp):
    """Sprint 5.18: legacy `provider` / `model` / `base_url` in the loaded
    config must be dropped on save — model_id is the new source of truth.
    """
    loaded_config = {
        "model_id": "openai:gpt-4o",
        "timeout": 180.0,
        "max_created_objects": 1000,
        "provider": "openai",           # ← legacy, must be dropped
        "model": "gpt-4o",              # ← legacy, must be dropped
        "base_url": "https://x/y",      # ← legacy, must be dropped
        "audit_log_enabled": True,
    }

    with patch("neurocad.ui.settings.load_config", return_value=loaded_config), \
         patch("neurocad.ui.settings.key_storage.load_key", return_value=(None, None)), \
         patch("neurocad.ui.settings.key_storage.available_backends", return_value=[]):
        dialog = SettingsDialog()
    _mock_ui(dialog, model_id="openai:gpt-4o", api_key="sk-x", tier="auto")
    dialog._config = loaded_config

    with patch("neurocad.ui.settings.key_storage.load_key", return_value=(None, None)), \
         patch("neurocad.ui.settings.save_config") as mock_save, \
         patch("neurocad.ui.settings.save_api_key",
               return_value=("System keyring", None)), \
         patch.object(dialog, "accept"):
        dialog._on_save()

    saved = mock_save.call_args.args[0]
    assert "provider" not in saved
    assert "model" not in saved
    assert "base_url" not in saved
    # Non-legacy non-UI field still present
    assert saved["audit_log_enabled"] is True


def test_load_current_shows_per_slug_backend(qapp):
    """Sprint 5.17: the status line shows the backend for the MODEL's key slug."""
    with patch("neurocad.ui.settings.load_config",
               return_value={"model_id": "deepseek:chat"}), \
         patch("neurocad.ui.settings.key_storage.load_key",
               return_value=("sk-ds", "macOS Keychain")) as mock_load, \
         patch("neurocad.ui.settings.key_storage.available_backends", return_value=[]):
        SettingsDialog()

    # load_key queried for the model's slug ("deepseek"), not "openai".
    slugs_queried = [c.args[0] for c in mock_load.call_args_list]
    assert "deepseek" in slugs_queried


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
