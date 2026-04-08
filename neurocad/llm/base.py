"""
Base LLM adapter interface.

Placeholder module; adapters and network calls will be added later.
"""

from abc import ABC, abstractmethod
from typing import Any


class LLMAdapter(ABC):
    """Abstract stub for LLM adapters."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        **kwargs: Any,
    ) -> str:
        """Return a stub response."""
        pass


class StubLLMAdapter(LLMAdapter):
    """Stub adapter for testing."""

    def generate(self, prompt: str, **kwargs: Any) -> str:
        return f"Stub response to: {prompt[:20]}..."
