"""ToolRepeatLimitToolset guard tests.

Verifies the per-tool repeat cap: under-limit calls delegate to the wrapped
toolset, the call past the limit raises ModelRetry without delegating, and counts
are tracked independently per tool name.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("LLM_MODEL_NAME", "test-model")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:1/v1")
os.environ.setdefault("OLLAMA_API_KEY", "sk-test")

from common.toolset_guards import ToolRepeatLimitToolset
from pydantic_ai.exceptions import ModelRetry

_LIMIT = 3


def _guard(wrapped: AsyncMock) -> ToolRepeatLimitToolset:
    return ToolRepeatLimitToolset(wrapped=wrapped, limit=_LIMIT)


async def test_under_limit_calls_delegate_to_wrapped() -> None:
    wrapped = AsyncMock()
    wrapped.call_tool = AsyncMock(return_value={"content": "ok"})
    guard = _guard(wrapped)
    ctx, tool = MagicMock(), MagicMock()

    for _ in range(_LIMIT):
        result = await guard.call_tool("get_journal", {}, ctx, tool)
        assert result == {"content": "ok"}
    assert wrapped.call_tool.await_count == _LIMIT


async def test_call_past_limit_raises_model_retry_without_delegating() -> None:
    wrapped = AsyncMock()
    wrapped.call_tool = AsyncMock(return_value={"content": "ok"})
    guard = _guard(wrapped)
    ctx, tool = MagicMock(), MagicMock()

    for _ in range(_LIMIT):
        await guard.call_tool("get_journal", {}, ctx, tool)

    with pytest.raises(ModelRetry):
        await guard.call_tool("get_journal", {}, ctx, tool)
    assert wrapped.call_tool.await_count == _LIMIT


async def test_distinct_tool_names_have_independent_counts() -> None:
    wrapped = AsyncMock()
    wrapped.call_tool = AsyncMock(return_value={"content": "ok"})
    guard = _guard(wrapped)
    ctx, tool = MagicMock(), MagicMock()

    for _ in range(_LIMIT):
        await guard.call_tool("get_journal", {}, ctx, tool)
    with pytest.raises(ModelRetry):
        await guard.call_tool("get_journal", {}, ctx, tool)

    for _ in range(_LIMIT):
        result = await guard.call_tool("get_pods", {}, ctx, tool)
        assert result == {"content": "ok"}
    assert wrapped.call_tool.await_count == 2 * _LIMIT
