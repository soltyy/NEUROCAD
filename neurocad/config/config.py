"""Configuration management."""

import json
from pathlib import Path
from typing import Any

from neurocad.config.defaults import (
    DEFAULT_AUDIT_LOG_ENABLED,
    DEFAULT_SNAPSHOT_MAX_CHARS,
)

from neurocad.config import key_storage

# Default registry ID. Lazy-imported from neurocad.llm.models to avoid a
# circular import (models -> ... -> config).
_DEFAULT_MODEL_ID = "openai:gpt-4o-mini"

# Legacy defaults — still written to config.json for backward compatibility
# (older versions of this code read them). New code reads `config["model_id"]`
# and ignores these; the Settings UI no longer exposes them.
DEFAULT_PROVIDER = "openai"
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TIMEOUT = 180.0
DEFAULT_MAX_CREATED_OBJECTS = 1000
DEFAULT_EXEC_HANDOFF_TIMEOUT_S = 60.0


def _get_config_dir() -> Path:
    """Determine the configuration directory using FreeCAD's user data location.

    Precedence:
    1. FreeCAD.ConfigGet("UserAppData")
    2. XDG‑style ~/.config/FreeCAD (if exists)
    3. Legacy ~/.freecad
    """
    try:
        import FreeCAD  # type: ignore
        user_app_data = FreeCAD.ConfigGet("UserAppData")
        if user_app_data:
            return Path(user_app_data) / "neurocad"
    except Exception:
        pass

    xdg_path = Path.home() / ".config" / "FreeCAD"
    if xdg_path.parent.exists():
        return xdg_path / "neurocad"

    return Path.home() / ".freecad" / "neurocad"


def _apply_defaults(data: dict[str, Any]) -> dict[str, Any]:
    """Fill missing keys with sensible defaults."""
    data.setdefault("model_id", _DEFAULT_MODEL_ID)
    data.setdefault("timeout", DEFAULT_TIMEOUT)
    data.setdefault("max_created_objects", DEFAULT_MAX_CREATED_OBJECTS)
    data.setdefault("audit_log_enabled", DEFAULT_AUDIT_LOG_ENABLED)
    data.setdefault("snapshot_max_chars", DEFAULT_SNAPSHOT_MAX_CHARS)
    data.setdefault("exec_handoff_timeout_s", DEFAULT_EXEC_HANDOFF_TIMEOUT_S)
    return data


def _migrate_legacy(data: dict[str, Any]) -> dict[str, Any]:
    """One-shot migration: if config has `provider`+`model`(+`base_url`) but no
    `model_id`, infer the registry id. Legacy fields are kept so older builds
    of the extension can still read the file, but new code uses `model_id`."""
    if "model_id" in data:
        return data
    # Lazy import — models.py cannot be imported at module level (circular).
    from neurocad.llm import models as _models
    spec = _models.infer_from_legacy_config(data)
    data["model_id"] = spec.id if spec else _models.default_model_id()
    return data


def load() -> dict[str, Any]:
    """Load configuration from JSON file.

    Returns:
        Dictionary with config values. Missing keys are filled from defaults.
    """
    config_file = _get_config_dir() / "config.json"
    if not config_file.exists():
        return _apply_defaults({})

    with open(config_file, encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    data = _migrate_legacy(data)
    return _apply_defaults(data)


def save(config: dict[str, Any]):
    """Save configuration to JSON file, omitting api_key."""
    config_dir = _get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)

    # Never write api_key to disk
    config = {k: v for k, v in config.items() if k != "api_key"}

    config_file = config_dir / "config.json"
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def save_api_key(
    provider: str,
    key: str,
    tier: str = key_storage.TIER_AUTOMATIC,
) -> tuple[str, str | None]:
    """Persist API key through the tiered key_storage chain.

    Returns `(backend_name_used, error_message_or_None)`. Unlike the previous
    implementation, this never raises — the UI receives a concrete storage
    tier name ("macOS Keychain", "Plaintext file (owner-only)", …) and can
    show that to the user instead of an alarming modal.

    tier:
      - key_storage.TIER_AUTOMATIC — try secure backends first, fall back to plaintext
      - key_storage.TIER_PLAINTEXT — force the plaintext file backend
      - key_storage.TIER_SESSION   — do not persist; caller holds the key in memory only
    """
    return key_storage.save_key(provider, key, tier=tier)


def load_api_key(provider: str) -> tuple[str | None, str | None]:
    """Return `(key, backend_name)` by trying every available backend.

    `None, None` if no backend has a stored key for the provider.
    """
    return key_storage.load_key(provider)


def delete_api_key(provider: str) -> list[str]:
    """Delete the stored key for `provider` from every available backend.

    Returns the list of backend names from which the key was actually removed.
    """
    return key_storage.delete_key(provider)
