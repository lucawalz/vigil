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
  LLM_REQUEST_TIMEOUT_S per-request read timeout. Must exceed real call latency
                        yet keep (1 + LLM_MAX_RETRIES) * timeout under the stage
                        budget (REMEDIATION_TIMEOUT_S / DIAGNOSIS_TIMEOUT_S) so a
                        stalled request fails fast and retries within budget
                        instead of consuming the whole stage. With the default
                        DIAGNOSIS_TIMEOUT_S of 300, set LLM_MAX_RETRIES=0.
  LLM_CONNECT_TIMEOUT_S connect timeout; short so a dead socket surfaces quickly.
  LLM_MAX_RETRIES       SDK-level retry cap on transient/timeout errors.

Hot-swap between providers by changing env vars -- no code changes needed:
  Ollama (local):  OLLAMA_BASE_URL=http://localhost:11434/v1
  Groq (dev):      OLLAMA_BASE_URL=https://api.groq.com/openai/v1

claude-* model names use the native Anthropic path (ANTHROPIC_API_KEY read from env).
"""

import os

import httpx
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

from .constants import (
    LLM_CONNECT_TIMEOUT_S,
    LLM_MAX_RETRIES,
    LLM_REQUEST_TIMEOUT_S,
)

DEFAULT_TEMPERATURE: float = 1.0
DEFAULT_REASONING_EFFORT: str = "none"


def build_model(
    model_name: str | None = None,
    model_options: dict | None = None,
    temperature: float = DEFAULT_TEMPERATURE,
) -> Model:
    """Return a pydantic-ai model configured from environment variables."""
    name = model_name or os.environ.get("LLM_MODEL_NAME", "test")
    timeout = httpx.Timeout(LLM_REQUEST_TIMEOUT_S, connect=LLM_CONNECT_TIMEOUT_S)
    if name.startswith("claude-"):
        settings = ModelSettings(temperature=temperature, **(model_options or {}))
        anthropic_client = AsyncAnthropic(max_retries=LLM_MAX_RETRIES, timeout=timeout)
        return AnthropicModel(
            name,
            provider=AnthropicProvider(anthropic_client=anthropic_client),
            settings=settings,
        )
    openai_settings = OpenAIChatModelSettings(temperature=temperature)
    effort = os.environ.get("LLM_REASONING_EFFORT", DEFAULT_REASONING_EFFORT).strip()
    if effort and effort.lower() != "default":
        openai_settings["openai_reasoning_effort"] = effort
    openai_settings.update(model_options or {})
    openai_client = AsyncOpenAI(
        base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        api_key=os.environ.get("OLLAMA_API_KEY", "nokey"),
        max_retries=LLM_MAX_RETRIES,
        timeout=timeout,
    )
    return OpenAIChatModel(
        name,
        provider=OpenAIProvider(openai_client=openai_client),
        settings=openai_settings,
    )
