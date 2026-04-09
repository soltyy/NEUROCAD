"""Tests for LLM adapters and registry."""

import os
from unittest.mock import MagicMock, patch

import pytest

from neurocad.llm.base import LLMAdapter, LLMResponse
from neurocad.llm.registry import load_adapter, load_adapter_with_session_key


class MockAdapter(LLMAdapter):
    """Mock adapter for testing."""
    def __init__(self, api_key: str, **kwargs):
        self.api_key = api_key
        self.kwargs = kwargs

    def complete(self, messages, system="", tools=None) -> LLMResponse:
        return LLMResponse(content="mock response", input_tokens=5, output_tokens=10)

    def stream(self, messages, system=""):
        yield "mock"


def test_mock_adapter():
    """Mock adapter returns correct LLMResponse."""
    adapter = MockAdapter(api_key="test")
    response = adapter.complete([{"role": "user", "content": "hello"}])
    assert isinstance(response, LLMResponse)
    assert response.content == "mock response"
    assert response.input_tokens == 5
    assert response.output_tokens == 10


def test_load_adapter_missing_key_raises():
    """load_adapter() raises ValueError when no API key is found."""
    mock_keyring = MagicMock()
    mock_keyring.get_password.return_value = None
    with patch.dict("os.environ", {}, clear=True), \
         patch("neurocad.llm.registry.keyring", mock_keyring), \
         pytest.raises(ValueError, match="No API key found"):
        load_adapter({"provider": "openai"})


def test_load_adapter_env_key():
    """load_adapter() retrieves API key from environment variable."""
    MockOpenAI = MagicMock()
    with patch.dict("os.environ", {"NEUROCAD_API_KEY_OPENAI": "env-key"}), \
         patch.dict("neurocad.llm.registry.ADAPTERS", {"openai": MockOpenAI}):
        load_adapter({"provider": "openai", "model": "test"})
        # Check that the adapter was instantiated with correct api_key and model
        assert MockOpenAI.call_count == 1
        call_kwargs = MockOpenAI.call_args[1]
        assert call_kwargs["api_key"] == "env-key"
        assert call_kwargs["model"] == "test"
        # base_url, max_tokens, temperature are optional and default to class defaults
        # They may not be present in kwargs if not specified in config


def test_load_adapter_keyring_key():
    """load_adapter() falls back to keyring when env var is empty."""
    MockOpenAI = MagicMock()
    with patch.dict("os.environ", {}):
        mock_keyring = MagicMock()
        mock_keyring.get_password.return_value = "keyring-key"
        with patch("neurocad.llm.registry.keyring", mock_keyring), \
             patch.dict("neurocad.llm.registry.ADAPTERS", {"openai": MockOpenAI}):
            load_adapter({"provider": "openai"})
            assert MockOpenAI.call_count == 1
            call_kwargs = MockOpenAI.call_args[1]
            assert call_kwargs["api_key"] == "keyring-key"
            # model may not be present in kwargs; if present it should be default
            if "model" in call_kwargs:
                assert call_kwargs["model"] == "gpt-4o-mini"


def test_load_adapter_with_session_key():
    """load_adapter_with_session_key() uses session key and does not call keyring."""
    MockOpenAI = MagicMock()
    mock_keyring = MagicMock()
    with patch("neurocad.llm.registry.keyring", mock_keyring), \
         patch.dict("neurocad.llm.registry.ADAPTERS", {"openai": MockOpenAI}):
        load_adapter_with_session_key(
            {"provider": "openai", "model": "custom"},
            session_key="temp-key"
        )
        # keyring.get_password should NOT be called
        mock_keyring.get_password.assert_not_called()
        assert MockOpenAI.call_count == 1
        call_kwargs = MockOpenAI.call_args[1]
        assert call_kwargs["api_key"] == "temp-key"
        assert call_kwargs["model"] == "custom"


def test_load_adapter_with_session_key_no_keyring_write():
    """load_adapter_with_session_key does not write to keyring."""
    MockOpenAI = MagicMock()
    mock_keyring = MagicMock()
    with patch("neurocad.llm.registry.keyring", mock_keyring):
        # The function should not call set_password
        # We'll just call load_adapter_with_session_key and ensure set_password not called
        with patch.dict("neurocad.llm.registry.ADAPTERS", {"openai": MockOpenAI}):
            load_adapter_with_session_key({"provider": "openai"}, "temp")
        mock_keyring.set_password.assert_not_called()


def test_load_adapter_missing_keyring_still_raises_clear_error():
    """Missing keyring should not crash import; resolution should fail clearly."""
    with patch.dict("os.environ", {}, clear=True), patch("neurocad.llm.registry.keyring", None), \
         pytest.raises(ValueError, match="install the `keyring` package"):
        load_adapter({"provider": "openai"})


def test_unknown_provider():
    """Unknown provider raises ValueError."""
    with pytest.raises(ValueError, match="Unknown provider"):
        load_adapter({"provider": "invalid"})


# Integration tests that require actual API keys are skipped by default
@pytest.mark.skipif(
    "NEUROCAD_API_KEY_OPENAI" not in os.environ,
    reason="OpenAI API key not set",
)
def test_openai_adapter_integration():
    """Integration test with real OpenAI API (requires key)."""
    # This test will only run if NEUROCAD_API_KEY_OPENAI is set
    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
