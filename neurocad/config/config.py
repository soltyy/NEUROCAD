"""Configuration management."""

import json
from pathlib import Path
from typing import Any

import keyring


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
        return {"provider": "openai", "model": "gpt-4o-mini"}

    with open(config_file, encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    # Ensure required keys exist
    data.setdefault("provider", "openai")
    data.setdefault("model", "gpt-4o-mini")
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
    keyring.set_password("neurocad", provider, key)
