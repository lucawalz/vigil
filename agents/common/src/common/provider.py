"""Multi-provider LLM factory built from environment variables.

Required env vars:
  OLLAMA_BASE_URL   Ollama-compatible provider endpoint (e.g. http://localhost:11434/v1)
  OLLAMA_API_KEY    Ollama-compatible provider API key
  LLM_MODEL_NAME    model identifier (e.g. llama3, claude-sonnet-4-6)

Optional env vars:
  LLM_REASONING_EFFORT  reasoning effort for OpenAI-compatible (Ollama) models:
                        none|minimal|low|medium|high. Defaults to "none" so
                        thinking models run without reasoning overhead; raise it
                        to enable test-time reasoning. "default" leaves the
                        provider default untouched. claude-* models ignore this
                        and run in standard (non-thinking) mode.

Hot-swap between providers by changing env vars -- no code changes needed:
  Ollama (local):  OLLAMA_BASE_URL=http://localhost:11434/v1
  Groq (dev):      OLLAMA_BASE_URL=https://api.groq.com/openai/v1

claude-* model names use the native Anthropic path (ANTHROPIC_API_KEY read from env).
"""

import os

from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

DEFAULT_TEMPERATURE: float = 1.0
DEFAULT_REASONING_EFFORT: str = "none"


def build_model(
    model_name: str | None = None,
    model_options: dict | None = None,
    temperature: float = DEFAULT_TEMPERATURE,
) -> Model:
    """Return a pydantic-ai model configured from environment variables."""
    name = model_name or os.environ.get("LLM_MODEL_NAME", "test")
    if name.startswith("claude-"):
        settings = ModelSettings(temperature=temperature, **(model_options or {}))
        return AnthropicModel(name, settings=settings)
    openai_settings = OpenAIChatModelSettings(temperature=temperature)
    effort = os.environ.get("LLM_REASONING_EFFORT", DEFAULT_REASONING_EFFORT).strip()
    if effort and effort.lower() != "default":
        openai_settings["openai_reasoning_effort"] = effort
    openai_settings.update(model_options or {})
    return OpenAIChatModel(
        name,
        provider=OpenAIProvider(
            base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            api_key=os.environ.get("OLLAMA_API_KEY", "nokey"),
        ),
        settings=openai_settings,
    )
