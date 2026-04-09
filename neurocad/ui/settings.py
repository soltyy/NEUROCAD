"""Settings dialog for provider selection and API key management."""

from ..config.config import load as load_config
from ..config.config import save as save_config
from ..config.config import save_api_key
from ..llm.registry import load_adapter_with_session_key
from .compat import QtWidgets


class SettingsDialog(QtWidgets.QDialog):
    """Dialog to configure LLM provider and API key."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NeuroCad Settings")
        self._config = load_config()
        self._adapter = None  # adapter created via Use once
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

        # API Key
        key_layout = QtWidgets.QHBoxLayout()
        key_layout.addWidget(QtWidgets.QLabel("API Key:"))
        self._api_key_edit = QtWidgets.QLineEdit()
        self._api_key_edit.setEchoMode(QtWidgets.QLineEdit.Password)
        key_layout.addWidget(self._api_key_edit, 1)
        layout.addLayout(key_layout)

        # Keyring warning (if missing)
        try:
            import keyring  # noqa: F401
            self._keyring_available = True
        except ImportError:
            self._keyring_available = False
            warning = QtWidgets.QLabel(
                "⚠️ Keyring package not installed. API keys cannot be saved securely. "
                "Use 'Use once' for temporary sessions, or install the keyring package."
            )
            warning.setWordWrap(True)
            warning.setStyleSheet("color: #f39c12;")
            layout.addWidget(warning)

        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        self._save_btn = QtWidgets.QPushButton("Save")
        self._use_once_btn = QtWidgets.QPushButton("Use once")
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

    def _load_current(self):
        """Load current config into UI."""
        self._provider_combo.setCurrentText(self._config.get("provider", "openai"))
        self._model_edit.setText(self._config.get("model", "gpt-4o-mini"))
        self._base_url_edit.setText(self._config.get("base_url", ""))
        # API key is not stored in config; leave blank
        self._api_key_edit.clear()

    def _on_provider_changed(self, provider):
        """Update model placeholder based on provider."""
        if provider == "openai":
            self._model_edit.setPlaceholderText("gpt-4o-mini")
        elif provider == "anthropic":
            self._model_edit.setPlaceholderText("claude-3-haiku-20240307")
        else:
            self._model_edit.setPlaceholderText("")

    def _collect_config(self) -> tuple[dict, str]:
        """Return config dict and API key from UI."""
        provider = self._provider_combo.currentText().strip()
        model = self._model_edit.text().strip()
        base_url = self._base_url_edit.text().strip()
        api_key = self._api_key_edit.text().strip()

        config = {"provider": provider}
        if model:
            config["model"] = model
        if base_url:
            config["base_url"] = base_url
        return config, api_key

    def _on_save(self):
        """Save config and API key (if keyring available)."""
        config, api_key = self._collect_config()
        if not api_key:
            QtWidgets.QMessageBox.warning(
                self,
                "Missing API Key",
                "Please enter an API key to save.",
            )
            return

        # Save config (without api_key)
        try:
            save_config(config)
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Save Failed",
                f"Could not save configuration: {e}",
            )
            return

        # Save API key via keyring
        try:
            save_api_key(config["provider"], api_key)
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                "Keyring Unavailable",
                f"Configuration saved, but API key could not be stored securely: {e}\n"
                "You will need to provide the key again next time.",
            )
        else:
            QtWidgets.QMessageBox.information(
                self,
                "Saved",
                "Settings and API key saved successfully.",
            )

        self._adapter = None
        self.accept()

    def _on_use_once(self):
        """Create adapter with session key (does not write to keyring)."""
        config, api_key = self._collect_config()
        if not api_key:
            QtWidgets.QMessageBox.warning(
                self,
                "Missing API Key",
                "Please enter an API key for this session.",
            )
            return

        try:
            adapter = load_adapter_with_session_key(config, api_key)
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Adapter Error",
                f"Could not create adapter: {e}",
            )
            return

        self._adapter = adapter
        QtWidgets.QMessageBox.information(
            self,
            "Adapter Ready",
            f"Adapter for {config['provider']} loaded for this session.\n"
            "The key will not be saved.",
        )
        self.accept()

    def get_adapter(self):
        """Return adapter created via Use once (or None if saved)."""
        return self._adapter
