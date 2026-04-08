"""
LLM adapter registry.

Placeholder module.
"""

from typing import Dict, Type

from neurocad.llm.base import LLMAdapter, StubLLMAdapter


class LLMRegistry:
    """Stub registry."""

    def __init__(self):
        self._adapters: Dict[str, Type[LLMAdapter]] = {}

    def register(self, name: str, adapter_cls: Type[LLMAdapter]) -> None:
        """Register a stub adapter."""
        self._adapters[name] = adapter_cls

    def get(self, name: str) -> Type[LLMAdapter]:
        """Return a stub adapter class."""
        return self._adapters.get(name, StubLLMAdapter)


# Global instance
registry = LLMRegistry()
