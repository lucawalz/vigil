"""Reusable WrapperToolset guards that intercept tool execution.

The guards subclass pydantic-ai's WrapperToolset so cross-cutting enforcement
(call budgets, circuit breakers) applies to any wrapped toolset without coupling
to a specific MCP client. State is held in a shared mutable counter so it survives
the dataclass copies that WrapperToolset.for_run / for_run_step produce per step.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic_ai._run_context import AgentDepsT, RunContext
from pydantic_ai.toolsets.abstract import ToolsetTool
from pydantic_ai.toolsets.wrapper import WrapperToolset


@dataclass
class _CallCounter:
    count: int = 0


@dataclass
class CallBudgetToolset(WrapperToolset[AgentDepsT]):
    """Caps invocations of a single tool within one run.

    Once tool_name has been called budget times, the next call raises on_exceeded
    instead of delegating to the wrapped toolset. Instantiate one per run so the
    counter starts fresh; the same instance must be reused for the whole run.
    """

    tool_name: str
    budget: int
    on_exceeded: type[Exception]
    _counter: _CallCounter = field(default_factory=_CallCounter)

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: RunContext[AgentDepsT],
        tool: ToolsetTool[AgentDepsT],
    ) -> Any:
        if name == self.tool_name:
            if self._counter.count >= self.budget:
                raise self.on_exceeded(
                    f"{self.tool_name} call budget of {self.budget} exhausted"
                )
            self._counter.count += 1
        return await self.wrapped.call_tool(name, tool_args, ctx, tool)
