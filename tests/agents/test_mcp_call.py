"""Per-call MCP timeout wrapper tests."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest
from common import mcp_call


async def test_call_tool_returns_result() -> None:
    server = AsyncMock()
    server.direct_call_tool = AsyncMock(return_value={"content": "ok"})

    result = await mcp_call.call_tool(server, "get_pods", {"namespace": "default"})

    assert result == {"content": "ok"}
    server.direct_call_tool.assert_awaited_once_with(
        "get_pods", {"namespace": "default"}
    )


async def test_call_tool_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mcp_call, "MCP_CALL_TIMEOUT_S", 0.05)

    async def _hang(*_args: object, **_kwargs: object) -> object:
        await asyncio.sleep(5)

    server = AsyncMock()
    server.direct_call_tool = _hang

    with pytest.raises(TimeoutError):
        await mcp_call.call_tool(server, "get_pods", {"namespace": "default"})
