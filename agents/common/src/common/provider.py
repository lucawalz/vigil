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

from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

DEFAULT_TEMPERATURE: float = 1.0


def build_model(
    model_name: str | None = None,
    model_options: dict | None = None,
    temperature: float = DEFAULT_TEMPERATURE,
) -> Model:
    """Return a pydantic-ai model configured from environment variables."""
    name = model_name or os.environ.get("LLM_MODEL_NAME", "test")
    settings = ModelSettings(temperature=temperature, **(model_options or {}))
    if name.startswith("claude-"):
        return AnthropicModel(name, settings=settings)
    return OpenAIChatModel(
        name,
        provider=OpenAIProvider(
            base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            api_key=os.environ.get("OLLAMA_API_KEY", "nokey"),
        ),
        settings=settings,
    )
