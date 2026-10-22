"""Per-call MCP timeout wrapper tests."""

from __future__ import annotations

import asyncio
import inspect
from unittest.mock import AsyncMock

import pytest
from common import mcp_call
from common.constants import MCP_CALL_TIMEOUT_S


async def test_call_tool_returns_result() -> None:
    server = AsyncMock()
    server.direct_call_tool = AsyncMock(return_value={"content": "ok"})

    result = await mcp_call.call_tool(server, "get_pods", {"namespace": "default"})

    assert result == {"content": "ok"}
    server.direct_call_tool.assert_awaited_once_with(
        "get_pods", {"namespace": "default"}
    )


def test_call_tool_defaults_to_mcp_call_timeout() -> None:
    timeout_param = inspect.signature(mcp_call.call_tool).parameters["timeout_s"]
    assert timeout_param.default == MCP_CALL_TIMEOUT_S


async def test_call_tool_honours_timeout_override() -> None:
    async def _hang(*_args: object, **_kwargs: object) -> object:
        await asyncio.sleep(5)

    server = AsyncMock()
    server.direct_call_tool = _hang

    with pytest.raises(TimeoutError):
        await mcp_call.call_tool(
            server, "get_pods", {"namespace": "default"}, timeout_s=0.05
        )
