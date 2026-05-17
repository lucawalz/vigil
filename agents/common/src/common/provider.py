"""Multi-provider LLM factory built from environment variables.

Required env vars:
  OLLAMA_BASE_URL   Ollama-compatible provider endpoint (e.g. http://localhost:11434/v1)
  OLLAMA_API_KEY    Ollama-compatible provider API key
  LLM_MODEL_NAME    model identifier (e.g. llama3, claude-sonnet-4-6)

Hot-swap between providers by changing env vars -- no code changes needed:
  Ollama (local):  OLLAMA_BASE_URL=http://localhost:11434/v1
  Groq (dev):      OLLAMA_BASE_URL=https://api.groq.com/openai/v1

claude-* model names use the native Anthropic path (ANTHROPIC_API_KEY read from env).
"""

import os

from pydantic_ai.models import Model, infer_model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings


def build_model(
    model_name: str | None = None,
    model_options: dict | None = None,
) -> Model:
    """Return a pydantic-ai model configured from environment variables."""
    name = model_name or os.environ.get("LLM_MODEL_NAME", "test")
    if name.startswith("claude-"):
        return infer_model(f"anthropic:{name}")
    settings = ModelSettings(**model_options) if model_options else None
    return OpenAIChatModel(
        name,
        provider=OpenAIProvider(
            base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            api_key=os.environ.get("OLLAMA_API_KEY", "nokey"),
        ),
        settings=settings,
    )
