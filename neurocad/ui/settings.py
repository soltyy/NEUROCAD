"""Settings dialog for provider selection and API key management.

Sprint 5.15 — tiered cross-platform key storage:
  • Radio-button storage choice (Automatic / Plaintext file / Session only).
  • Inline status label showing which backend was actually used on save.
  • No more alarming modal dialogs on every save.
"""

from ..config import key_storage
from ..config.config import load as load_config
from ..config.config import save as save_config
from ..config.config import save_api_key
from ..llm.registry import load_adapter_with_session_key
from .compat import Qt, QtWidgets


class SettingsDialog(QtWidgets.QDialog):
    """Dialog to configure LLM provider and API key."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NeuroCAD Settings")
        self._config = load_config()
        self._adapter = None  # adapter created via Session only
        self._build_ui()
        self._connect_signals()
        self._load_current()

    def _build_ui(self):
        """Create UI elements."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Provider
        provider_layout = QtWidgets.QHBoxLayout()
        provider_layout.addWidget(QtWidgets.QLabel("Provider:"))
        self._provider_combo = QtWidgets.QComboBox()
        self._provider_combo.addItems(["openai", "anthropic"])
        provider_layout.addWidget(self._provider_combo, 1)
        layout.addLayout(provider_layout)

        # Model
        model_layout = QtWidgets.QHBoxLayout()
        model_layout.addWidget(QtWidgets.QLabel("Model:"))
        self._model_edit = QtWidgets.QLineEdit()
        model_layout.addWidget(self._model_edit, 1)
        layout.addLayout(model_layout)

        # Base URL (optional)
        url_layout = QtWidgets.QHBoxLayout()
        url_layout.addWidget(QtWidgets.QLabel("Base URL (optional):"))
        self._base_url_edit = QtWidgets.QLineEdit()
        self._base_url_edit.setPlaceholderText("https://api.openai.com/v1")
        url_layout.addWidget(self._base_url_edit, 1)
        layout.addLayout(url_layout)

        # Timeout
        timeout_layout = QtWidgets.QHBoxLayout()
        timeout_layout.addWidget(QtWidgets.QLabel("LLM timeout (s):"))
        self._timeout_spin = QtWidgets.QDoubleSpinBox()
        self._timeout_spin.setRange(1.0, 600.0)
        self._timeout_spin.setDecimals(0)
        self._timeout_spin.setSingleStep(5.0)
        timeout_layout.addWidget(self._timeout_spin, 1)
        layout.addLayout(timeout_layout)

        # Max created objects
        max_objects_layout = QtWidgets.QHBoxLayout()
        max_objects_layout.addWidget(QtWidgets.QLabel("Max created objects per request:"))
        self._max_objects_spin = QtWidgets.QSpinBox()
        self._max_objects_spin.setRange(1, 10000)
        self._max_objects_spin.setSingleStep(100)
        max_objects_layout.addWidget(self._max_objects_spin, 1)
        layout.addLayout(max_objects_layout)

        # Authentication group
        auth_group = QtWidgets.QGroupBox("Authentication")
        auth_layout = QtWidgets.QVBoxLayout()
        auth_layout.setContentsMargins(8, 12, 8, 12)
        auth_layout.setSpacing(8)

        # API Key
        key_layout = QtWidgets.QHBoxLayout()
        key_layout.addWidget(QtWidgets.QLabel("API Key:"))
        self._api_key_edit = QtWidgets.QLineEdit()
        self._api_key_edit.setEchoMode(QtWidgets.QLineEdit.Password)
        key_layout.addWidget(self._api_key_edit, 1)
        auth_layout.addLayout(key_layout)

        # Storage tier — radio buttons
        self._tier_group = QtWidgets.QButtonGroup(self)
        self._tier_auto = QtWidgets.QRadioButton("Automatic (recommended)")
        self._tier_auto.setToolTip(
            "Use the most secure backend available on this OS: "
            "Python keyring → macOS Keychain → Linux secret-tool → "
            "plaintext file. Falls through automatically."
        )
        self._tier_plaintext = QtWidgets.QRadioButton("Plaintext file (owner-only)")
        self._tier_plaintext.setToolTip(
            "Store as JSON file in the config dir, chmod 0600 (readable only by "
            "your user). Works on every platform without extra packages."
        )
        self._tier_session = QtWidgets.QRadioButton("Session only (do not save)")
        self._tier_session.setToolTip(
            "Use the key for this FreeCAD session only. Key is not written anywhere."
        )
        self._tier_group.addButton(self._tier_auto, 0)
        self._tier_group.addButton(self._tier_plaintext, 1)
        self._tier_group.addButton(self._tier_session, 2)
        self._tier_auto.setChecked(True)

        tier_box = QtWidgets.QVBoxLayout()
        tier_label = QtWidgets.QLabel("Storage:")
        tier_box.addWidget(tier_label)
        tier_box.addWidget(self._tier_auto)
        tier_box.addWidget(self._tier_plaintext)
        tier_box.addWidget(self._tier_session)
        auth_layout.addLayout(tier_box)

        # Inline status — where the key IS / WAS stored. Replaces the modal.
        self._storage_status = QtWidgets.QLabel("")
        self._storage_status.setWordWrap(True)
        self._storage_status.setStyleSheet("padding: 4px; font-size: 10pt;")
        auth_layout.addWidget(self._storage_status)

        auth_group.setLayout(auth_layout)
        layout.addWidget(auth_group)

        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        self._save_btn = QtWidgets.QPushButton("Save")
        self._save_btn.setToolTip(
            "Save configuration and persist the API key using the selected storage tier."
        )
        self._use_once_btn = QtWidgets.QPushButton("Use once")
        self._use_once_btn.setToolTip(
            "Create a temporary adapter for this session; key is NOT saved."
        )
        self._cancel_btn = QtWidgets.QPushButton("Cancel")
        button_layout.addWidget(self._save_btn)
        button_layout.addWidget(self._use_once_btn)
        button_layout.addStretch()
        button_layout.addWidget(self._cancel_btn)
        layout.addLayout(button_layout)

    def _connect_signals(self):
        """Connect UI signals."""
        self._save_btn.clicked.connect(self._on_save)
        self._use_once_btn.clicked.connect(self._on_use_once)
        self._cancel_btn.clicked.connect(self.reject)
        self._provider_combo.currentTextChanged.connect(self._on_provider_changed)

    def _available_backends_summary(self) -> str:
        names = [b.name for b in key_storage.available_backends()]
        return " → ".join(names) if names else "none"

    def _load_current(self):
        """Load current config into UI and show current key-storage status."""
        self._provider_combo.setCurrentText(self._config.get("provider", "openai"))
        self._model_edit.setText(self._config.get("model", "gpt-4o-mini"))
        self._base_url_edit.setText(self._config.get("base_url", ""))
        self._timeout_spin.setValue(float(self._config.get("timeout", 180.0)))
        self._max_objects_spin.setValue(int(self._config.get("max_created_objects", 1000)))
        # API key field is always empty on load — we never echo stored keys.
        self._api_key_edit.clear()

        # Neutral informational status before any save.
        _key, backend = key_storage.load_key(self._config.get("provider", "openai"))
        if backend:
            self._set_status(
                f"🔑 Key currently stored in: <b>{backend}</b>. "
                f"Leave the field blank to keep it, or enter a new key to replace it.",
                "#0b8",
            )
        else:
            self._set_status(
                f"No saved key for this provider. "
                f"Available storage tiers: {self._available_backends_summary()}.",
                "#888",
            )

    def _on_provider_changed(self, provider):
        """Update model placeholder based on provider and refresh status line."""
        if provider == "openai":
            self._model_edit.setPlaceholderText("gpt-4o-mini")
        elif provider == "anthropic":
            self._model_edit.setPlaceholderText("claude-3-haiku-20240307")
        else:
            self._model_edit.setPlaceholderText("")

        _key, backend = key_storage.load_key(provider)
        if backend:
            self._set_status(
                f"🔑 Key for <b>{provider}</b> currently stored in: <b>{backend}</b>.",
                "#0b8",
            )
        else:
            self._set_status(
                f"No saved key for <b>{provider}</b>. "
                f"Available storage tiers: {self._available_backends_summary()}.",
                "#888",
            )

    def _set_status(self, html: str, color: str = "#666") -> None:
        self._storage_status.setTextFormat(Qt.RichText)
        self._storage_status.setText(html)
        self._storage_status.setStyleSheet(f"color: {color}; padding: 4px; font-size: 10pt;")

    def _collect_config(self) -> tuple[dict, str]:
        """Return config dict and API key from UI."""
        provider = self._provider_combo.currentText().strip()
        model = self._model_edit.text().strip()
        base_url = self._base_url_edit.text().strip()
        timeout = float(self._timeout_spin.value())
        max_objects = self._max_objects_spin.value()
        api_key = self._api_key_edit.text().strip()

        config = {"provider": provider, "timeout": timeout, "max_created_objects": max_objects}
        if model:
            config["model"] = model
        if base_url:
            config["base_url"] = base_url
        return config, api_key

    def _selected_tier(self) -> str:
        if self._tier_plaintext.isChecked():
            return key_storage.TIER_PLAINTEXT
        if self._tier_session.isChecked():
            return key_storage.TIER_SESSION
        return key_storage.TIER_AUTOMATIC

    def _on_save(self):
        """Save config and API key using the selected storage tier.

        Reports the outcome inline (no modal) unless there is nothing to save.
        """
        config, api_key = self._collect_config()
        tier = self._selected_tier()

        if not api_key:
            self._set_status("⚠️ Please enter an API key before saving.", "#e67e22")
            return

        # Save config (never includes api_key).
        try:
            save_config(config)
        except Exception as e:
            self._set_status(f"❌ Could not save configuration: {e}", "#c0392b")
            return

        # "Session only" tier — build an adapter now, do NOT persist the key.
        if tier == key_storage.TIER_SESSION:
            try:
                adapter = load_adapter_with_session_key(config, api_key)
            except Exception as e:
                self._set_status(f"❌ Could not create adapter: {e}", "#c0392b")
                return
            self._adapter = adapter
            self._set_status(
                "🔑 Settings saved. Key kept in <b>session memory only</b> — "
                "you will need to provide it again next time.",
                "#0b8",
            )
            self.accept()
            return

        # Automatic / Plaintext — persist via key_storage.
        backend_name, err = save_api_key(config["provider"], api_key, tier=tier)
        if err:
            self._set_status(
                f"❌ Could not persist the key: {err}. Try a different storage tier.",
                "#c0392b",
            )
            return

        self._adapter = None
        if "Plaintext" in backend_name:
            self._set_status(
                f"🔑 Settings saved. Key persisted to <b>{backend_name}</b> — "
                f"file is readable only by your OS user.",
                "#e67e22",
            )
        else:
            self._set_status(
                f"🔑 Settings saved. Key persisted to <b>{backend_name}</b>.",
                "#0b8",
            )
        self.accept()

    def _on_use_once(self):
        """Shortcut for the Session-only tier — build adapter without persisting."""
        config, api_key = self._collect_config()
        if not api_key:
            self._set_status("⚠️ Please enter an API key for this session.", "#e67e22")
            return

        try:
            adapter = load_adapter_with_session_key(config, api_key)
        except Exception as e:
            self._set_status(f"❌ Could not create adapter: {e}", "#c0392b")
            return

        self._adapter = adapter
        self._set_status(
            f"🔑 Temporary adapter for <b>{config['provider']}</b> ready. "
            f"Key is not saved.",
            "#0b8",
        )
        self.accept()

    def get_adapter(self):
        """Return adapter created via Use once / Session only (or None if Save path)."""
        return self._adapter
