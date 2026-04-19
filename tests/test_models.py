"""Sprint 5.17 — tests for the curated model registry."""

from __future__ import annotations

import pytest

from neurocad.llm import models


def test_list_models_returns_non_empty():
    specs = models.list_models()
    assert len(specs) >= 5  # OpenAI × 2 + Anthropic × 2 + DeepSeek × 2 + Ollama
    ids = [s.id for s in specs]
    assert "openai:gpt-4o-mini" in ids
    assert "deepseek:chat" in ids


def test_get_model_found():
    spec = models.get_model("deepseek:reasoner")
    assert spec is not None
    assert spec.display_name == "DeepSeek Reasoner (R1-style CoT)"
    assert spec.adapter == "openai"
    assert spec.base_url == "https://api.deepseek.com/v1"
    assert spec.key_slug == "deepseek"
    assert spec.file_handling == models.FILE_HANDLING_INLINE


def test_get_model_unknown_returns_none():
    assert models.get_model("fake:model") is None


def test_default_model_id_is_registered():
    assert models.get_model(models.default_model_id()) is not None


def test_deepseek_uses_openai_adapter_but_different_key_slug():
    """Sprint 5.17: DeepSeek uses OpenAI-compatible API (adapter='openai')
    but its API key must be stored under 'deepseek' — a separate account.
    """
    chat = models.get_model("deepseek:chat")
    assert chat is not None
    assert chat.adapter == "openai"       # wire-compatible
    assert chat.key_slug == "deepseek"    # separate credential

    openai = models.get_model("openai:gpt-4o-mini")
    assert openai.adapter == "openai"
    assert openai.key_slug == "openai"


def test_infer_from_legacy_deepseek_by_base_url():
    spec = models.infer_from_legacy_config({
        "provider": "openai",
        "model": "deepseek-chat",
        "base_url": "https://api.deepseek.com/v1",
    })
    assert spec is not None
    assert spec.id == "deepseek:chat"


def test_infer_from_legacy_deepseek_reasoner_by_base_url():
    spec = models.infer_from_legacy_config({
        "provider": "openai",
        "model": "deepseek-reasoner",
        "base_url": "https://api.deepseek.com/v1",
    })
    assert spec is not None
    assert spec.id == "deepseek:reasoner"


def test_infer_from_legacy_ollama_by_base_url():
    spec = models.infer_from_legacy_config({
        "provider": "openai",
        "model": "llama3.1",
        "base_url": "http://localhost:11434/v1",
    })
    assert spec is not None
    assert spec.id == "ollama:llama3.1"


def test_infer_from_legacy_openai_no_base_url_by_model_name():
    spec = models.infer_from_legacy_config({
        "provider": "openai",
        "model": "gpt-4o",
    })
    assert spec is not None
    assert spec.id == "openai:gpt-4o"


def test_infer_from_legacy_anthropic_provider_fallback():
    spec = models.infer_from_legacy_config({
        "provider": "anthropic",
        "model": "claude-unknown-model-string",
    })
    assert spec is not None
    # Falls back to the cheap Haiku default for the provider.
    assert spec.id == "anthropic:claude-3-5-haiku"


def test_infer_from_legacy_unknown_returns_none():
    spec = models.infer_from_legacy_config({
        "provider": "sometotalgarbage",
        "model": "nothing",
    })
    assert spec is None


def test_build_file_attachment_prompt_inline_deepseek():
    spec = models.get_model("deepseek:chat")
    out = models.build_file_attachment_prompt(
        spec, "Summarize this.",
        file_name="report.md",
        file_content="# Title\nBody text",
    )
    assert "[file name]: report.md" in out
    assert "[file content begin]" in out
    assert "# Title" in out
    assert "[file content end]" in out
    assert "Summarize this." in out


def test_build_file_attachment_prompt_native_model_raises():
    spec = models.get_model("openai:gpt-4o")
    with pytest.raises(ValueError, match="native file upload"):
        models.build_file_attachment_prompt(
            spec, "q", file_name="f.txt", file_content="x",
        )


def test_build_file_attachment_prompt_no_support_raises():
    spec = models.get_model("ollama:llama3.1")
    with pytest.raises(ValueError, match="does not support file attachments"):
        models.build_file_attachment_prompt(
            spec, "q", file_name="f.txt", file_content="x",
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
