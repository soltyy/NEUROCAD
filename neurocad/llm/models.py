"""Curated model registry.

Sprint 5.17: the user picks a concrete LLM ("DeepSeek Chat", "Claude 3.5
Sonnet", "GPT-4o") instead of juggling a provider slug + model name + base
URL. Each `ModelSpec` carries everything an adapter needs plus metadata
for per-model behavior (context window, file-handling strategy).

Key-storage slug is separate from adapter class: DeepSeek uses the OpenAI
adapter class (API is wire-compatible) but its API key is stored under
`"deepseek"`, not `"openai"`. Same for Ollama (local, no key).
"""

from __future__ import annotations

from dataclasses import dataclass

# --- File-handling strategies ---------------------------------------------

# Model accepts native file uploads via its provider's file API (e.g. OpenAI
# Assistants API, Anthropic Files API). Use the provider-native call.
FILE_HANDLING_NATIVE = "native"

# Model has no file-upload endpoint; we must embed the file's text content
# directly into the prompt using `file_embed_template`. DeepSeek requires
# this approach per their documentation.
FILE_HANDLING_INLINE = "inline"

# Model has no file support at all — reject attempts to attach files.
FILE_HANDLING_NONE = "none"


DEEPSEEK_INLINE_TEMPLATE = (
    "[file name]: {file_name}\n"
    "[file content begin]\n"
    "{file_content}\n"
    "[file content end]\n"
    "{question}"
)


@dataclass(frozen=True)
class ModelSpec:
    """Canonical description of a concrete LLM offering.

    Fields:
      id:          stable registry key, e.g. "deepseek:chat".
      display_name: shown in the Settings dropdown.
      adapter:     adapter class name — "openai" or "anthropic".
      model_id:    model identifier sent to the API.
      base_url:    API base URL (None = adapter's default).
      key_slug:    key_storage account name; DeepSeek != OpenAI even though
                   they share the openai adapter class.
      context_window: approximate token budget (informational).
      file_handling:   FILE_HANDLING_* constant.
      file_embed_template: template with {file_name}/{file_content}/{question}
                   placeholders. Only required when file_handling == "inline".
      notes:       one-line description for the UI.
    """

    id: str
    display_name: str
    adapter: str
    model_id: str
    base_url: str | None
    key_slug: str
    context_window: int
    file_handling: str
    file_embed_template: str | None
    notes: str


# --- The curated list ------------------------------------------------------

MODELS: tuple[ModelSpec, ...] = (
    # ------------------ OpenAI --------------------------------------------
    ModelSpec(
        id="openai:gpt-4o",
        display_name="GPT-4o (OpenAI)",
        adapter="openai",
        model_id="gpt-4o",
        base_url=None,
        key_slug="openai",
        context_window=128_000,
        file_handling=FILE_HANDLING_NATIVE,
        file_embed_template=None,
        notes="Fast, general-purpose flagship.",
    ),
    ModelSpec(
        id="openai:gpt-4o-mini",
        display_name="GPT-4o mini (OpenAI, cheap)",
        adapter="openai",
        model_id="gpt-4o-mini",
        base_url=None,
        key_slug="openai",
        context_window=128_000,
        file_handling=FILE_HANDLING_NATIVE,
        file_embed_template=None,
        notes="Cheap fallback; OK for simple CAD tasks.",
    ),
    # ------------------ Anthropic -----------------------------------------
    ModelSpec(
        id="anthropic:claude-3-5-sonnet",
        display_name="Claude 3.5 Sonnet (Anthropic)",
        adapter="anthropic",
        model_id="claude-3-5-sonnet-20241022",
        base_url=None,
        key_slug="anthropic",
        context_window=200_000,
        file_handling=FILE_HANDLING_NATIVE,
        file_embed_template=None,
        notes="Strong on code + multi-step CAD.",
    ),
    ModelSpec(
        id="anthropic:claude-3-5-haiku",
        display_name="Claude 3.5 Haiku (Anthropic, cheap)",
        adapter="anthropic",
        model_id="claude-3-5-haiku-20241022",
        base_url=None,
        key_slug="anthropic",
        context_window=200_000,
        file_handling=FILE_HANDLING_NATIVE,
        file_embed_template=None,
        notes="Cheap Anthropic fallback.",
    ),
    # ------------------ DeepSeek (OpenAI-compatible) -----------------------
    ModelSpec(
        id="deepseek:chat",
        display_name="DeepSeek Chat",
        adapter="openai",                         # wire-compatible with OpenAI
        model_id="deepseek-chat",
        base_url="https://api.deepseek.com/v1",
        key_slug="deepseek",                      # separate key from OpenAI
        context_window=64_000,
        file_handling=FILE_HANDLING_INLINE,
        file_embed_template=DEEPSEEK_INLINE_TEMPLATE,
        notes="Cheap general-purpose. Files embedded in the prompt.",
    ),
    ModelSpec(
        id="deepseek:reasoner",
        display_name="DeepSeek Reasoner (R1-style CoT)",
        adapter="openai",
        model_id="deepseek-reasoner",
        base_url="https://api.deepseek.com/v1",
        key_slug="deepseek",
        context_window=64_000,
        file_handling=FILE_HANDLING_INLINE,
        file_embed_template=DEEPSEEK_INLINE_TEMPLATE,
        notes="Chain-of-thought reasoning model.",
    ),
    # ------------------ Ollama (local) ------------------------------------
    ModelSpec(
        id="ollama:llama3.1",
        display_name="Llama 3.1 (Ollama, local)",
        adapter="openai",                         # Ollama exposes OpenAI-compatible API
        model_id="llama3.1",
        base_url="http://localhost:11434/v1",
        key_slug="ollama",                        # local — any dummy key works
        context_window=8_192,
        file_handling=FILE_HANDLING_NONE,
        file_embed_template=None,
        notes="Local-only via Ollama. Start `ollama serve` first.",
    ),
)


# --- Lookup helpers --------------------------------------------------------

def list_models() -> list[ModelSpec]:
    """Return all known models, preserving registry order."""
    return list(MODELS)


def get_model(model_id: str) -> ModelSpec | None:
    """Look up a model by its registry id. Returns None if not found."""
    for spec in MODELS:
        if spec.id == model_id:
            return spec
    return None


def default_model_id() -> str:
    """Conservative default: the cheapest OpenAI-family choice."""
    return "openai:gpt-4o-mini"


def infer_from_legacy_config(config: dict) -> ModelSpec | None:
    """Migrate legacy `provider` + `model` + `base_url` triples to a ModelSpec.

    Returns None if we can't guess; the caller should then fall back to
    default_model_id().
    """
    legacy_model = str(config.get("model", "") or "").strip().lower()
    legacy_base = str(config.get("base_url", "") or "").strip().lower()

    # 1. Base URL trumps everything (DeepSeek is the canonical example).
    if "deepseek" in legacy_base:
        if "reason" in legacy_model:
            return get_model("deepseek:reasoner")
        return get_model("deepseek:chat")

    if "ollama" in legacy_base or "localhost:11434" in legacy_base:
        return get_model("ollama:llama3.1")

    # 2. Match model id literally against the registry.
    for spec in MODELS:
        if spec.model_id.lower() == legacy_model:
            return spec
        if spec.id == legacy_model:
            return spec

    # 3. Provider-level fallback.
    provider = str(config.get("provider", "") or "").strip().lower()
    if provider == "openai":
        return get_model("openai:gpt-4o-mini")
    if provider == "anthropic":
        return get_model("anthropic:claude-3-5-haiku")

    return None


# --- File embedding helper (T-5.17E) --------------------------------------

def build_file_attachment_prompt(
    spec: ModelSpec,
    question: str,
    file_name: str,
    file_content: str,
) -> str:
    """Format a user prompt that carries an attached file's content.

    For models with ``file_handling == "inline"`` (DeepSeek) the file content
    is embedded directly in the prompt using ``spec.file_embed_template``.
    For native-file-upload models the caller should use the provider's file
    API instead — this helper raises ValueError to force that path.

    NeuroCAD currently has no file-attachment UI; this helper is scaffolding
    for a future attachment feature.
    """
    if spec.file_handling == FILE_HANDLING_NONE:
        raise ValueError(
            f"{spec.display_name} does not support file attachments."
        )
    if spec.file_handling == FILE_HANDLING_NATIVE:
        raise ValueError(
            f"{spec.display_name} supports native file upload — use the "
            "provider's file API instead of inline embedding."
        )
    if spec.file_handling == FILE_HANDLING_INLINE:
        if not spec.file_embed_template:
            raise ValueError(
                f"{spec.display_name} declares inline file handling but has no "
                "file_embed_template — registry bug."
            )
        return spec.file_embed_template.format(
            file_name=file_name,
            file_content=file_content,
            question=question,
        )
    raise ValueError(f"Unknown file_handling mode: {spec.file_handling!r}")
