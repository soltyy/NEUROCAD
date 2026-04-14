"""Build system prompt from document snapshot."""

from neurocad.config.config import load
from neurocad.config.defaults import DEFAULT_SYSTEM_PROMPT

from .context import DocSnapshot, to_prompt_str


def build_system(snap: DocSnapshot) -> str:
    """Return a system prompt that describes the current document state."""
    config = load()
    max_chars = config.get("snapshot_max_chars", 1500)
    snapshot_desc = to_prompt_str(snap, max_chars=max_chars)
    return f"{snapshot_desc}\n\n{DEFAULT_SYSTEM_PROMPT}"
