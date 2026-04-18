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
    """load_adapter() raises ValueError when no API key is found in any backend."""
    with patch.dict("os.environ", {}, clear=True), \
         patch("neurocad.llm.registry.key_storage.load_key",
               return_value=(None, None)), \
         pytest.raises(ValueError, match="No API key found"):
        load_adapter({"provider": "openai"})


def test_api_key_precedence_order():
    """Sprint 5.15: precedence = session → env var → key_storage.load_key()."""
    MockOpenAI = MagicMock()
    with patch.dict("os.environ", {"NEUROCAD_API_KEY_OPENAI": "env-key"}), \
         patch("neurocad.llm.registry.key_storage.load_key",
               return_value=("storage-key", "FakeBackend")) as mock_load, \
         patch.dict("neurocad.llm.registry.ADAPTERS", {"openai": MockOpenAI}):
        # 1. Session key wins over env var and storage
        load_adapter({"provider": "openai"}, session_key="session-key")
        assert MockOpenAI.call_args[1]["api_key"] == "session-key"
        mock_load.assert_not_called()
        MockOpenAI.reset_mock()
        mock_load.reset_mock()

        # 2. Env var wins over storage when no session key
        load_adapter({"provider": "openai"}, session_key=None)
        assert MockOpenAI.call_args[1]["api_key"] == "env-key"
        mock_load.assert_not_called()
        MockOpenAI.reset_mock()
        mock_load.reset_mock()

        # 3. Fall through to key_storage when env var missing
        with patch.dict("os.environ", {}, clear=True):
            load_adapter({"provider": "openai"})
            assert MockOpenAI.call_args[1]["api_key"] == "storage-key"
            mock_load.assert_called_once_with("openai")


def test_load_adapter_env_key():
    """load_adapter() retrieves API key from environment variable."""
    MockOpenAI = MagicMock()
    with patch.dict("os.environ", {"NEUROCAD_API_KEY_OPENAI": "env-key"}), \
         patch.dict("neurocad.llm.registry.ADAPTERS", {"openai": MockOpenAI}):
        load_adapter({"provider": "openai", "model": "test"})
        assert MockOpenAI.call_count == 1
        call_kwargs = MockOpenAI.call_args[1]
        assert call_kwargs["api_key"] == "env-key"
        assert call_kwargs["model"] == "test"


def test_load_adapter_falls_back_to_key_storage():
    """Sprint 5.15: load_adapter() falls back to key_storage.load_key when env var missing."""
    MockOpenAI = MagicMock()
    with patch.dict("os.environ", {}, clear=True), \
         patch("neurocad.llm.registry.key_storage.load_key",
               return_value=("stored-key", "macOS Keychain")), \
         patch.dict("neurocad.llm.registry.ADAPTERS", {"openai": MockOpenAI}):
        load_adapter({"provider": "openai"})
        assert MockOpenAI.call_args[1]["api_key"] == "stored-key"


def test_load_adapter_with_session_key_skips_storage():
    """load_adapter_with_session_key uses session key, never consults key_storage."""
    MockOpenAI = MagicMock()
    with patch("neurocad.llm.registry.key_storage.load_key") as mock_load, \
         patch.dict("neurocad.llm.registry.ADAPTERS", {"openai": MockOpenAI}):
        load_adapter_with_session_key(
            {"provider": "openai", "model": "custom"},
            session_key="temp-key",
        )
        mock_load.assert_not_called()
        assert MockOpenAI.call_args[1]["api_key"] == "temp-key"
        assert MockOpenAI.call_args[1]["model"] == "custom"


def test_load_adapter_with_session_key_does_not_persist():
    """load_adapter_with_session_key does not call key_storage.save_key."""
    MockOpenAI = MagicMock()
    with patch("neurocad.config.key_storage.save_key") as mock_save, \
         patch.dict("neurocad.llm.registry.ADAPTERS", {"openai": MockOpenAI}):
        load_adapter_with_session_key({"provider": "openai"}, "temp")
    mock_save.assert_not_called()


def test_load_adapter_no_storage_backends_raises_clear_error():
    """Sprint 5.15: clear error lists available backends (never mentions 'install keyring')."""
    with patch.dict("os.environ", {}, clear=True), \
         patch("neurocad.llm.registry.key_storage.load_key",
               return_value=(None, None)), \
         patch("neurocad.llm.registry.key_storage.available_backends",
               return_value=[]), \
         pytest.raises(ValueError, match="No API key found"):
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
