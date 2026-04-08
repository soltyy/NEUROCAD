"""Conversation history management."""

from enum import StrEnum
from typing import Any


class Role(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    FEEDBACK = "feedback"


class History:
    """Stores a sequence of messages with roles."""

    def __init__(self):
        self._items: list[dict[str, Any]] = []

    def add(self, role: Role, content: str):
        """Append a message."""
        self._items.append({"role": role, "content": content})

    def to_llm_messages(self) -> list[dict[str, str]]:
        """Convert history to OpenAI‑style messages.

        FEEDBACK messages are mapped to "user" role.
        """
        messages = []
        for item in self._items:
            role = item["role"]
            if role == Role.FEEDBACK:
                role = "user"
            messages.append({"role": role, "content": item["content"]})
        return messages

    @property
    def items(self):
        """Return raw items."""
        return self._items.copy()

    def clear(self):
        """Remove all messages."""
        self._items.clear()
