"""
Default configuration values.

Placeholder module.
"""
from pathlib import Path

# Default configuration values as defined in sprint plan.
DEFAULTS = {
    "provider": "openai",
    "model": "gpt-4",
    "base_url": "https://api.openai.com/v1",
    "max_tokens": 2048,
    "temperature": 0.7,
}

# Path to the configuration file (platform-specific).
CONFIG_PATH = Path.home() / ".freecad" / "neurocad" / "config.json"
