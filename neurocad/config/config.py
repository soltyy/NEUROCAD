"""Configuration management."""

import json
from pathlib import Path
from typing import Any

from neurocad.config.defaults import (
    DEFAULT_AUDIT_LOG_ENABLED,
    DEFAULT_SNAPSHOT_MAX_CHARS,
)

try:
    import keyring
except ImportError:
    keyring = None  # type: ignore[assignment]


DEFAULT_PROVIDER = "openai"
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TIMEOUT = 180.0
DEFAULT_MAX_CREATED_OBJECTS = 1000


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


def load() -> dict[str, Any]:
    """Load configuration from JSON file.

    Returns:
        Dictionary with config values. Missing keys are filled from defaults.
    """
    config_file = _get_config_dir() / "config.json"
    if not config_file.exists():
        return {
            "provider": DEFAULT_PROVIDER,
            "model": DEFAULT_MODEL,
            "timeout": DEFAULT_TIMEOUT,
            "max_created_objects": DEFAULT_MAX_CREATED_OBJECTS,
            "audit_log_enabled": DEFAULT_AUDIT_LOG_ENABLED,
            "snapshot_max_chars": DEFAULT_SNAPSHOT_MAX_CHARS,
        }

    with open(config_file, encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    # Ensure required keys exist
    data.setdefault("provider", DEFAULT_PROVIDER)
    data.setdefault("model", DEFAULT_MODEL)
    data.setdefault("timeout", DEFAULT_TIMEOUT)
    data.setdefault("max_created_objects", DEFAULT_MAX_CREATED_OBJECTS)
    data.setdefault("audit_log_enabled", DEFAULT_AUDIT_LOG_ENABLED)
    data.setdefault("snapshot_max_chars", DEFAULT_SNAPSHOT_MAX_CHARS)
    return data


def save(config: dict[str, Any]):
    """Save configuration to JSON file, omitting api_key."""
    config_dir = _get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)

    # Never write api_key to disk
    config = {k: v for k, v in config.items() if k != "api_key"}

    config_file = config_dir / "config.json"
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def save_api_key(provider: str, key: str):
    """Store API key in system keyring (outside config file)."""
    if keyring is None:
        raise RuntimeError(
            "keyring is not installed in the active FreeCAD Python environment. "
            "Install the project dependencies or use an environment variable/session key."
        )
    keyring.set_password("neurocad", provider, key)
