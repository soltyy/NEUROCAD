"""
Configuration loading and persistence.

Placeholder module; persistence logic will be added later.
"""

import json
import logging
from typing import Any, Dict

from .defaults import CONFIG_PATH, DEFAULTS

logger = logging.getLogger(__name__)


def load() -> Dict[str, Any]:
    """
    Load configuration from file, merging with defaults.

    Returns:
        Configuration dictionary. Unknown keys are filtered out.
        The api_key is stripped from the returned dict.
    """
    config = DEFAULTS.copy()

    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                file_data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Could not read config file %s: %s", CONFIG_PATH, e)
            file_data = {}

        # Filter unknown keys (only those present in DEFAULTS)
        filtered = {k: v for k, v in file_data.items() if k in DEFAULTS}
        config.update(filtered)

        # Strip api_key (should not be stored in plain config)
        config.pop("api_key", None)

    return config


def save(cfg: Dict[str, Any]) -> None:
    """
    Save configuration to file, stripping api_key before writing.

    Args:
        cfg: Configuration dictionary to save.
    """
    # Remove api_key from the saved configuration
    cfg = cfg.copy()
    cfg.pop("api_key", None)

    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except OSError as e:
        logger.error("Could not write config file %s: %s", CONFIG_PATH, e)


def save_api_key(api_key: str) -> None:
    """
    Save API key securely using keyring.

    Args:
        api_key: The API key to store.
    """
    try:
        import keyring
        keyring.set_password("neurocad", "api_key", api_key)
    except ImportError:
        logger.warning("keyring not installed; cannot store API key securely")
