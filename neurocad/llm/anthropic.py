"""Anthropic Claude adapter."""

from collections.abc import Iterator

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
        """Send a request and get a single response."""
        try:
            import anthropic  # type: ignore[import-not-found]
        except ImportError as e:
            raise ImportError(
                "Anthropic SDK not installed. Run `pip install anthropic`."
            ) from e

        client = anthropic.Anthropic(api_key=self.api_key)
        extra_kwargs = {}
        if tools is not None:
            extra_kwargs["tools"] = tools
        # Anthropic expects system as separate parameter
        response = client.messages.create(
            model=self.model,
            system=system,
            messages=messages,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            **extra_kwargs,
        )
        return LLMResponse(
            content=response.content[0].text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            stop_reason=response.stop_reason,
        )

    def stream(self, messages, system="") -> Iterator[str]:
        """Stream tokens from the LLM."""
        try:
            import anthropic  # type: ignore[import-not-found]
        except ImportError as e:
            raise ImportError(
                "Anthropic SDK not installed. Run `pip install anthropic`."
            ) from e

        client = anthropic.Anthropic(api_key=self.api_key)
        stream = client.messages.create(
            model=self.model,
            system=system,
            messages=messages,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            stream=True,
        )
        for chunk in stream:
            if chunk.type == "content_block_delta":
                yield chunk.delta.text
