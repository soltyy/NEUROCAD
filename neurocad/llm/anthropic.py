"""Anthropic Claude adapter."""

from .base import LLMAdapter, LLMResponse


class AnthropicAdapter(LLMAdapter):
    """Adapter for Anthropic Claude API."""

    def __init__(self, api_key: str, model: str = "claude-3-haiku-20240307",
                 max_tokens: int = 4096, temperature: float = 0.0):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    def complete(self, messages, system="", tools=None) -> LLMResponse:
        # Implementation will be added in Sprint 2
        raise NotImplementedError("AnthropicAdapter.complete not implemented")

    def stream(self, messages, system=""):
        # Implementation will be added in Sprint 2
        raise NotImplementedError("AnthropicAdapter.stream not implemented")
