"""Routing unit tests for build_model()."""

from __future__ import annotations

import os
from unittest.mock import patch

os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:1/v1")
os.environ.setdefault("OLLAMA_API_KEY", "nokey")
os.environ.setdefault("LLM_MODEL_NAME", "test-model")

from common.provider import build_model


def test_anthropic_path_returns_anthropic_model() -> None:
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test-fake"}):
        m = build_model("claude-sonnet-4-6")
    assert type(m).__name__ == "AnthropicModel"


def test_ollama_path_returns_openai_chat_model() -> None:
    env = {"OLLAMA_BASE_URL": "http://localhost:11434/v1", "OLLAMA_API_KEY": "nokey"}
    with patch.dict(os.environ, env):
        m = build_model("llama3")
    assert type(m).__name__ == "OpenAIChatModel"


def test_default_name_uses_env_var() -> None:
    env = {
        "LLM_MODEL_NAME": "llama3",
        "OLLAMA_BASE_URL": "http://localhost:11434/v1",
        "OLLAMA_API_KEY": "nokey",
    }
    with patch.dict(os.environ, env):
        m = build_model()
    assert type(m).__name__ == "OpenAIChatModel"


def test_build_model_anthropic_default_temperature() -> None:
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test-fake"}):
        m = build_model("claude-sonnet-4-6")
    assert m.settings is not None
    assert m.settings.get("temperature") == 1.0


def test_build_model_anthropic_explicit_temperature() -> None:
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test-fake"}):
        m = build_model("claude-sonnet-4-6", temperature=0.5)
    assert m.settings is not None
    assert m.settings.get("temperature") == 0.5


def test_build_model_openai_default_temperature() -> None:
    env = {"OLLAMA_BASE_URL": "http://localhost:11434/v1", "OLLAMA_API_KEY": "nokey"}
    with patch.dict(os.environ, env):
        m = build_model("ollama/llama")
    assert m.settings is not None
    assert m.settings.get("temperature") == 1.0


def test_build_model_openai_explicit_temperature() -> None:
    env = {"OLLAMA_BASE_URL": "http://localhost:11434/v1", "OLLAMA_API_KEY": "nokey"}
    with patch.dict(os.environ, env):
        m = build_model("ollama/llama", temperature=0.3)
    assert m.settings is not None
    assert m.settings.get("temperature") == 0.3


def test_build_model_openai_defaults_reasoning_effort_none() -> None:
    env = {"OLLAMA_BASE_URL": "http://localhost:11434/v1", "OLLAMA_API_KEY": "nokey"}
    with patch.dict(os.environ, env):
        os.environ.pop("LLM_REASONING_EFFORT", None)
        m = build_model("ollama/llama")
    assert m.settings is not None
    assert m.settings.get("openai_reasoning_effort") == "none"


def test_build_model_openai_respects_reasoning_effort_env() -> None:
    env = {
        "OLLAMA_BASE_URL": "http://localhost:11434/v1",
        "OLLAMA_API_KEY": "nokey",
        "LLM_REASONING_EFFORT": "high",
    }
    with patch.dict(os.environ, env):
        m = build_model("ollama/llama")
    assert m.settings is not None
    assert m.settings.get("openai_reasoning_effort") == "high"


def test_build_model_openai_default_keyword_leaves_effort_unset() -> None:
    env = {
        "OLLAMA_BASE_URL": "http://localhost:11434/v1",
        "OLLAMA_API_KEY": "nokey",
        "LLM_REASONING_EFFORT": "default",
    }
    with patch.dict(os.environ, env):
        m = build_model("ollama/llama")
    assert m.settings is not None
    assert "openai_reasoning_effort" not in m.settings


def test_build_model_anthropic_ignores_reasoning_effort() -> None:
    env = {"ANTHROPIC_API_KEY": "sk-ant-test-fake", "LLM_REASONING_EFFORT": "high"}
    with patch.dict(os.environ, env):
        m = build_model("claude-sonnet-4-6")
    assert m.settings is not None
    assert "openai_reasoning_effort" not in m.settings


def test_build_model_openai_client_bounds_timeout_and_retries() -> None:
    env = {
        "OLLAMA_BASE_URL": "http://localhost:11434/v1",
        "OLLAMA_API_KEY": "nokey",
        "LLM_REQUEST_TIMEOUT_S": "240",
        "LLM_CONNECT_TIMEOUT_S": "10",
        "LLM_MAX_RETRIES": "1",
    }
    with patch.dict(os.environ, env):
        from common.constants import (
            LLM_CONNECT_TIMEOUT_S,
            LLM_MAX_RETRIES,
            LLM_REQUEST_TIMEOUT_S,
        )

        m = build_model("ollama/llama")
    assert m.client.max_retries == LLM_MAX_RETRIES
    assert m.client.timeout.read == LLM_REQUEST_TIMEOUT_S
    assert m.client.timeout.connect == LLM_CONNECT_TIMEOUT_S


def test_build_model_anthropic_client_bounds_timeout_and_retries() -> None:
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test-fake"}):
        from common.constants import (
            LLM_CONNECT_TIMEOUT_S,
            LLM_MAX_RETRIES,
            LLM_REQUEST_TIMEOUT_S,
        )

        m = build_model("claude-sonnet-4-6")
    assert m.client.max_retries == LLM_MAX_RETRIES
    assert m.client.timeout.read == LLM_REQUEST_TIMEOUT_S
    assert m.client.timeout.connect == LLM_CONNECT_TIMEOUT_S
