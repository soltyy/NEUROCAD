"""OpenAI‑compatible adapter (OpenAI, Ollama, local)."""

from .base import LLMAdapter, LLMResponse


class OpenAIAdapter(LLMAdapter):
    """Adapter for OpenAI‑compatible APIs."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini",
                 base_url: str = "https://api.openai.com/v1",
                 max_tokens: int = 4096, temperature: float = 0.0):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.max_tokens = max_tokens
        self.temperature = temperature

    def complete(self, messages, system="", tools=None) -> LLMResponse:
        # Implementation will be added in Sprint 2
        raise NotImplementedError("OpenAIAdapter.complete not implemented")

    def stream(self, messages, system=""):
        # Implementation will be added in Sprint 2
        raise NotImplementedError("OpenAIAdapter.stream not implemented")
