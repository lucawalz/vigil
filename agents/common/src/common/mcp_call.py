"""Timeout-bounded wrapper around MCP direct_call_tool invocations."""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic_ai.mcp import MCPServerStdio

from .constants import MCP_CALL_TIMEOUT_S


async def call_tool(
    server: MCPServerStdio,
    name: str,
    args: dict[str, Any],
    *,
    timeout_s: float = MCP_CALL_TIMEOUT_S,
) -> object:
    """Invoke an MCP tool, raising TimeoutError after timeout_s.

    Bounds a single hung MCP server so it cannot stall a run for the full
    outer run timeout. Callers handle TimeoutError the same way they handle
    other transport failures; tools that block on purpose pass a longer
    timeout_s.
    """
    async with asyncio.timeout(timeout_s):
        return await server.direct_call_tool(name, args)
