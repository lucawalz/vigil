"""Tests for the ToolRepeatLimitToolset and GlobalToolCallBudgetToolset guards.

Verifies the per-tool repeat cap: under-limit calls delegate to the wrapped
toolset, the call past the limit raises ModelRetry without delegating, and counts
are tracked independently per tool name. Also verifies the global soft budget:
under-threshold calls delegate, the threshold-th call raises ModelRetry naming the
DiagnosisReport without delegating, and a shared counter accumulates across
distinct wrapper instances.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("LLM_MODEL_NAME", "test-model")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:1/v1")
os.environ.setdefault("OLLAMA_API_KEY", "sk-test")

from common.toolset_guards import (
    GlobalToolCallBudgetToolset,
    GlobalToolCounter,
    ToolRepeatLimitToolset,
)
from pydantic_ai.exceptions import ModelRetry

_LIMIT = 3
_THRESHOLD = 3


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


def _budget_guard(
    wrapped: AsyncMock, counter: GlobalToolCounter | None = None
) -> GlobalToolCallBudgetToolset:
    if counter is None:
        return GlobalToolCallBudgetToolset(wrapped=wrapped, threshold=_THRESHOLD)
    return GlobalToolCallBudgetToolset(
        wrapped=wrapped, threshold=_THRESHOLD, counter=counter
    )


async def test_budget_under_threshold_calls_delegate_to_wrapped() -> None:
    wrapped = AsyncMock()
    wrapped.call_tool = AsyncMock(return_value={"content": "ok"})
    guard = _budget_guard(wrapped)
    ctx, tool = MagicMock(), MagicMock()

    for _ in range(_THRESHOLD):
        result = await guard.call_tool("get_journal", {}, ctx, tool)
        assert result == {"content": "ok"}
    assert wrapped.call_tool.await_count == _THRESHOLD


async def test_budget_threshold_call_raises_model_retry_naming_report() -> None:
    wrapped = AsyncMock()
    wrapped.call_tool = AsyncMock(return_value={"content": "ok"})
    guard = _budget_guard(wrapped)
    ctx, tool = MagicMock(), MagicMock()

    for _ in range(_THRESHOLD):
        await guard.call_tool("get_journal", {}, ctx, tool)

    with pytest.raises(ModelRetry, match="DiagnosisReport"):
        await guard.call_tool("get_pods", {}, ctx, tool)
    assert wrapped.call_tool.await_count == _THRESHOLD


async def test_budget_does_not_delegate_for_rejected_request() -> None:
    wrapped = AsyncMock()
    wrapped.call_tool = AsyncMock(return_value={"content": "ok"})
    guard = _budget_guard(wrapped)
    ctx, tool = MagicMock(), MagicMock()

    for _ in range(_THRESHOLD):
        await guard.call_tool("get_journal", {}, ctx, tool)

    with pytest.raises(ModelRetry):
        await guard.call_tool("get_journal", {}, ctx, tool)
    assert wrapped.call_tool.await_count == _THRESHOLD


async def test_shared_counter_accumulates_globally_across_instances() -> None:
    counter = GlobalToolCounter()
    wrapped_a = AsyncMock()
    wrapped_a.call_tool = AsyncMock(return_value={"content": "ok"})
    wrapped_b = AsyncMock()
    wrapped_b.call_tool = AsyncMock(return_value={"content": "ok"})
    guard_a = _budget_guard(wrapped_a, counter)
    guard_b = _budget_guard(wrapped_b, counter)
    ctx, tool = MagicMock(), MagicMock()

    for _ in range(_THRESHOLD - 1):
        await guard_a.call_tool("get_journal", {}, ctx, tool)
    await guard_b.call_tool("get_pods", {}, ctx, tool)
    assert counter.total == _THRESHOLD

    with pytest.raises(ModelRetry, match="DiagnosisReport"):
        await guard_b.call_tool("get_pods", {}, ctx, tool)
    assert wrapped_b.call_tool.await_count == 1
