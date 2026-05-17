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
