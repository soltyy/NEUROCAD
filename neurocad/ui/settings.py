"""Settings dialog — Sprint 5.17: single Model dropdown + per-slug API key status.

The user picks a concrete LLM by display name ("DeepSeek Chat", "Claude 3.5
Sonnet", …). Provider/adapter, base URL, and key_storage slug are looked up
from `neurocad.llm.models.MODELS`. The API key is stored under the model's
`key_slug` (so DeepSeek key ≠ OpenAI key even when both use the openai
adapter class).

Tiered storage (Sprint 5.15) is preserved — three radio buttons:
Automatic / Plaintext file / Session only. Inline status line replaces the
old alarming modal.
"""

from ..config import key_storage
from ..config.config import load as load_config
from ..config.config import save as save_config
from ..config.config import save_api_key
from ..llm import models as model_registry
from ..llm.registry import load_adapter_with_session_key
from .compat import Qt, QtWidgets


class SettingsDialog(QtWidgets.QDialog):
    """Dialog to configure the active LLM model and its API key."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NeuroCAD Settings")
        self._config = load_config()
        self._adapter = None  # adapter created via Session only
        self._build_ui()
        self._connect_signals()
        self._load_current()

    # --- UI -----------------------------------------------------------

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Model dropdown (replaces old provider / model / base_url triple).
        model_layout = QtWidgets.QHBoxLayout()
        model_layout.addWidget(QtWidgets.QLabel("Model:"))
        self._model_combo = QtWidgets.QComboBox()
        for spec in model_registry.list_models():
            # userData stores the registry id; display text shows the name + hint.
            label = f"{spec.display_name}"
            if spec.notes:
                label += f"  —  {spec.notes}"
            self._model_combo.addItem(label, userData=spec.id)
        model_layout.addWidget(self._model_combo, 1)
        layout.addLayout(model_layout)

        # Per-model info label: adapter / base URL / context window / file handling
        self._model_info = QtWidgets.QLabel("")
        self._model_info.setWordWrap(True)
        self._model_info.setStyleSheet("color: #666; padding: 2px 4px; font-size: 9pt;")
        layout.addWidget(self._model_info)

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

        # Storage tier radio
        self._tier_group = QtWidgets.QButtonGroup(self)
        self._tier_auto = QtWidgets.QRadioButton("Automatic (recommended)")
        self._tier_auto.setToolTip(
            "Use the most secure backend available on this OS: "
            "Python keyring → macOS Keychain → Linux secret-tool → plaintext file."
        )
        self._tier_plaintext = QtWidgets.QRadioButton("Plaintext file (owner-only)")
        self._tier_plaintext.setToolTip(
            "JSON file in config dir, chmod 0600. Works on every platform, no pip deps."
        )
        self._tier_session = QtWidgets.QRadioButton("Session only (do not save)")
        self._tier_session.setToolTip(
            "Use the key for this FreeCAD session only. Not written to disk."
        )
        self._tier_group.addButton(self._tier_auto, 0)
        self._tier_group.addButton(self._tier_plaintext, 1)
        self._tier_group.addButton(self._tier_session, 2)
        self._tier_auto.setChecked(True)

        tier_box = QtWidgets.QVBoxLayout()
        tier_box.addWidget(QtWidgets.QLabel("Storage:"))
        tier_box.addWidget(self._tier_auto)
        tier_box.addWidget(self._tier_plaintext)
        tier_box.addWidget(self._tier_session)
        auth_layout.addLayout(tier_box)

        # Inline status — replaces the old alarming modal.
        self._storage_status = QtWidgets.QLabel("")
        self._storage_status.setWordWrap(True)
        self._storage_status.setTextFormat(Qt.RichText)
        self._storage_status.setStyleSheet("padding: 4px; font-size: 10pt;")
        auth_layout.addWidget(self._storage_status)

        auth_group.setLayout(auth_layout)
        layout.addWidget(auth_group)

        # Sprint 6.0 — agent v2 toggle
        v2_group = QtWidgets.QGroupBox("Agent architecture")
        v2_layout = QtWidgets.QVBoxLayout()
        self._use_v2_check = QtWidgets.QCheckBox(
            "Use plan-driven agent v2 (Sprint 6.0, experimental)"
        )
        self._use_v2_check.setToolTip(
            "Multi-pass agent: clarifies missing info, builds a structured "
            "DesignIntent plan, executes step-by-step with a generic contract "
            "verifier on each step. Falls back to legacy single-pass agent "
            "when unchecked."
        )
        v2_layout.addWidget(self._use_v2_check)
        self._legacy_anti_check = QtWidgets.QCheckBox(
            "Enable legacy per-class anti-patterns (wheel/axle/gear/house)"
        )
        self._legacy_anti_check.setToolTip(
            "Sprint 5.x validator anti-patterns. v2 users typically disable "
            "these — the DesignIntent verifier replaces them. Kept on by "
            "default for backward compatibility."
        )
        v2_layout.addWidget(self._legacy_anti_check)
        v2_group.setLayout(v2_layout)
        layout.addWidget(v2_group)

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
        self._save_btn.clicked.connect(self._on_save)
        self._use_once_btn.clicked.connect(self._on_use_once)
        self._cancel_btn.clicked.connect(self.reject)
        self._model_combo.currentIndexChanged.connect(self._on_model_changed)

    # --- state --------------------------------------------------------

    def _current_spec(self) -> model_registry.ModelSpec | None:
        mid = self._model_combo.currentData()
        return model_registry.get_model(mid) if mid else None

    def _available_backends_summary(self) -> str:
        names = [b.name for b in key_storage.available_backends()]
        return " → ".join(names) if names else "none"

    def _load_current(self):
        """Populate UI from config and show per-model key-storage status."""
        self._timeout_spin.setValue(float(self._config.get("timeout", 180.0)))
        self._max_objects_spin.setValue(int(self._config.get("max_created_objects", 1000)))
        self._use_v2_check.setChecked(bool(self._config.get("use_agent_v2", False)))
        self._legacy_anti_check.setChecked(bool(self._config.get("legacy_anti_patterns", True)))

        # Pick active model: explicit model_id → legacy inference → default.
        mid = self._config.get("model_id") or model_registry.default_model_id()
        spec = model_registry.get_model(mid)
        if spec is None:
            spec = model_registry.infer_from_legacy_config(self._config)
        if spec is None:
            spec = model_registry.get_model(model_registry.default_model_id())
        assert spec is not None
        idx = self._model_combo.findData(spec.id)
        if idx >= 0:
            self._model_combo.setCurrentIndex(idx)

        self._api_key_edit.clear()
        self._refresh_model_info(spec)
        self._refresh_storage_status(spec)

    def _on_model_changed(self, _index: int):
        spec = self._current_spec()
        if spec is None:
            return
        self._refresh_model_info(spec)
        self._refresh_storage_status(spec)

    def _refresh_model_info(self, spec: model_registry.ModelSpec):
        base = spec.base_url or "(provider default)"
        fh = spec.file_handling
        self._model_info.setText(
            f"Adapter: {spec.adapter}  ·  Base URL: {base}  ·  "
            f"Context: {spec.context_window:,} tokens  ·  Files: {fh}  ·  "
            f"Key slug: {spec.key_slug}"
        )

    def _refresh_storage_status(self, spec: model_registry.ModelSpec):
        stored_key, backend = key_storage.load_key(spec.key_slug)
        if backend:
            self._set_status(
                f"🔑 Key for <b>{spec.key_slug}</b> currently stored in: "
                f"<b>{backend}</b>. Leave the field blank to keep it, or "
                f"enter a new key to replace it.",
                "#0b8",
            )
        else:
            self._set_status(
                f"No saved key for <b>{spec.key_slug}</b>. "
                f"Available storage tiers: {self._available_backends_summary()}.",
                "#888",
            )

    def _set_status(self, html: str, color: str = "#666") -> None:
        self._storage_status.setText(html)
        self._storage_status.setStyleSheet(f"color: {color}; padding: 4px; font-size: 10pt;")

    # --- submit -------------------------------------------------------

    # Legacy fields replaced by `model_id` in Sprint 5.17; drop them on save
    # so a freshly-written config doesn't carry conflicting provider/model/
    # base_url triples from an old migration.
    _LEGACY_FIELDS_TO_DROP: frozenset[str] = frozenset({"provider", "model", "base_url"})

    def _collect_config(self) -> tuple[dict, str, model_registry.ModelSpec | None]:
        """Build the full config to save.

        Sprint 5.18 fix: merge UI-editable fields into the loaded config
        (`self._config`) instead of replacing it. Previously, fields not
        exposed in the dialog (`audit_log_enabled`, `snapshot_max_chars`,
        `exec_handoff_timeout_s`) were silently wiped on Save — "editing
        the config must not spoil it".
        """
        spec = self._current_spec()
        timeout = float(self._timeout_spin.value())
        max_objects = self._max_objects_spin.value()
        api_key = self._api_key_edit.text().strip()

        # Start from the loaded config so non-UI fields are preserved.
        merged: dict = {
            k: v for k, v in self._config.items()
            if k not in self._LEGACY_FIELDS_TO_DROP and k != "api_key"
        }
        # Overlay the fields the user can edit in the dialog.
        merged["model_id"] = spec.id if spec else model_registry.default_model_id()
        merged["timeout"] = timeout
        merged["max_created_objects"] = max_objects
        merged["use_agent_v2"] = bool(self._use_v2_check.isChecked())
        merged["legacy_anti_patterns"] = bool(self._legacy_anti_check.isChecked())

        return merged, api_key, spec

    def _selected_tier(self) -> str:
        if self._tier_plaintext.isChecked():
            return key_storage.TIER_PLAINTEXT
        if self._tier_session.isChecked():
            return key_storage.TIER_SESSION
        return key_storage.TIER_AUTOMATIC

    def _on_save(self):
        config, api_key, spec = self._collect_config()
        if spec is None:
            self._set_status("⚠️ No model selected.", "#e67e22")
            return

        tier = self._selected_tier()

        if not api_key:
            # Maybe a key is already stored; user just wants to save non-key
            # settings. Accept if a key exists for this slug, otherwise warn.
            existing_key, _backend = key_storage.load_key(spec.key_slug)
            if not existing_key and tier != key_storage.TIER_SESSION:
                self._set_status(
                    "⚠️ Please enter an API key before saving.", "#e67e22",
                )
                return
            # Save only the non-key config and close.
            try:
                save_config(config)
            except Exception as e:
                self._set_status(f"❌ Could not save configuration: {e}", "#c0392b")
                return
            self._set_status(
                "🔑 Settings saved. Existing API key retained.", "#0b8",
            )
            self.accept()
            return

        # Save the non-key config first.
        try:
            save_config(config)
        except Exception as e:
            self._set_status(f"❌ Could not save configuration: {e}", "#c0392b")
            return

        # Session-only tier — do not persist the key; build adapter now.
        if tier == key_storage.TIER_SESSION:
            try:
                adapter = load_adapter_with_session_key(config, api_key)
            except Exception as e:
                self._set_status(f"❌ Could not create adapter: {e}", "#c0392b")
                return
            self._adapter = adapter
            self._set_status(
                "🔑 Settings saved. Key kept in <b>session memory only</b>.",
                "#0b8",
            )
            self.accept()
            return

        backend_name, err = save_api_key(spec.key_slug, api_key, tier=tier)
        if err:
            self._set_status(
                f"❌ Could not persist the key: {err}. Try a different storage tier.",
                "#c0392b",
            )
            return

        self._adapter = None
        if "Plaintext" in backend_name:
            self._set_status(
                f"🔑 Settings saved. Key for <b>{spec.key_slug}</b> persisted to "
                f"<b>{backend_name}</b> — file readable only by your OS user.",
                "#e67e22",
            )
        else:
            self._set_status(
                f"🔑 Settings saved. Key for <b>{spec.key_slug}</b> persisted to "
                f"<b>{backend_name}</b>.",
                "#0b8",
            )
        self.accept()

    def _on_use_once(self):
        config, api_key, spec = self._collect_config()
        if spec is None:
            self._set_status("⚠️ No model selected.", "#e67e22")
            return
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
            f"🔑 Temporary adapter for <b>{spec.display_name}</b> ready. "
            f"Key is not saved.",
            "#0b8",
        )
        self.accept()

    def get_adapter(self):
        """Return the adapter built via Use once / Session only (or None for Save path)."""
        return self._adapter
