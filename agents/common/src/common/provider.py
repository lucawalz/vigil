"""OpenAI-compatible LLM provider built from environment variables.

Required env vars:
  LLM_BASE_URL    provider endpoint (e.g. https://api.groq.com/openai/v1)
  LLM_API_KEY     provider API key
  LLM_MODEL_NAME  model identifier (e.g. llama-3.3-70b-versatile)

Hot-swap between providers by changing env vars -- no code changes needed:
  Groq (dev):      LLM_BASE_URL=https://api.groq.com/openai/v1
  Ollama Cloud:    LLM_BASE_URL=https://api.ollama.com/v1
  Anthropic:       LLM_BASE_URL=https://api.anthropic.com/v1
"""

import os

from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider


def build_model() -> OpenAIChatModel:
    """Return a pydantic-ai model configured from environment variables."""
    return OpenAIChatModel(
        os.environ.get("LLM_MODEL_NAME", "test"),
        provider=OpenAIProvider(
            base_url=os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1"),
            api_key=os.environ.get("LLM_API_KEY", "nokey"),
        ),
    )
