"""OpenAI-compatible adapter (OpenAI, DeepSeek, Ollama, local)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from ..core.debug import log_error, log_info
from .base import LLMAdapter, LLMResponse


class OpenAIAdapter(LLMAdapter):
    """Adapter for OpenAI-compatible chat completion APIs."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        max_tokens: int = 4096,
        temperature: float = 0.0,
        timeout: float = 20.0,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout

    def _endpoint(self) -> str:
        """Return the chat completions endpoint."""
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _payload(
        self,
        messages: list[dict[str, str]],
        system: str = "",
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
    ) -> dict[str, Any]:
        if system:
            messages = [{"role": "system", "content": system}] + messages
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": stream,
        }
        if tools is not None:
            payload["tools"] = tools
        return payload

    def complete(self, messages, system="", tools=None) -> LLMResponse:
        """Send a request and get a single response."""
        log_info(
            "adapter.openai",
            "starting complete request",
            model=self.model,
            base_url=self.base_url,
            message_count=len(messages),
            system_chars=len(system),
            timeout=self.timeout,
        )
        try:
            import httpx  # type: ignore[import-not-found]
        except ImportError as e:
            log_error("adapter.openai", "httpx import failed", error=e)
            raise ImportError(
                "httpx is not installed in the active FreeCAD Python environment."
            ) from e

        timeout = httpx.Timeout(connect=5.0, read=self.timeout, write=10.0, pool=5.0)
        payload = self._payload(messages, system=system, tools=tools, stream=False)

        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    self._endpoint(),
                    headers=self._headers(),
                    json=payload,
                )
                response.raise_for_status()
        except Exception as e:
            log_error("adapter.openai", "request failed", error=e, endpoint=self._endpoint())
            raise

        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError(f"OpenAI-compatible response missing choices: {data}")

        choice = choices[0]
        message = choice.get("message") or {}
        content = message.get("content") or ""
        usage = data.get("usage") or {}
        log_info(
            "adapter.openai",
            "request completed",
            finish_reason=choice.get("finish_reason"),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            content_preview=content[:200],
        )
        return LLMResponse(
            content=content,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            stop_reason=choice.get("finish_reason"),
        )

    def stream(self, messages, system="") -> Iterator[str]:
        """Streaming is not used in the current Sprint 2 pipeline."""
        raise NotImplementedError("Streaming is disabled in the current pipeline.")
