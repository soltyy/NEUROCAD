"""LLM adapter protocol."""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class LLMResponse:
    """Structured response from an LLM."""
    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    stop_reason: str | None = None


class LLMAdapter(Protocol):
    """Protocol for LLM providers."""

    def complete(
        self,
        messages: list[dict[str, str]],
        system: str = "",
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Send a request and get a single response."""
        ...

    def stream(
        self,
        messages: list[dict[str, str]],
        system: str = "",
    ) -> Iterator[str]:
        """Stream tokens from the LLM."""
        ...
