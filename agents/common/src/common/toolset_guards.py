"""Reusable WrapperToolset guards that intercept tool execution.

The guards subclass pydantic-ai's WrapperToolset so cross-cutting enforcement
(call budgets, circuit breakers) applies to any wrapped toolset without coupling
to a specific MCP client. State is held in a shared mutable counter so it survives
the dataclass copies that WrapperToolset.for_run / for_run_step produce per step.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from pydantic_ai._run_context import AgentDepsT, RunContext
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.toolsets.abstract import ToolsetTool
from pydantic_ai.toolsets.wrapper import WrapperToolset


class CircuitBreakerTripped(Exception):
    """Raised when consecutive failed MCP tool calls reach the breaker threshold.

    Counted per run across diagnosis and remediation; a successful tool call
    resets the count. Propagates out of the agent loop to abort the run.
    """


@runtime_checkable
class Breaker(Protocol):
    """Minimal failure-counting contract a CircuitBreakerToolset drives.

    Decoupling from the orchestrator's concrete breaker avoids a circular import:
    the guard depends only on success()/error(), not on orchestrator internals.
    """

    def success(self) -> None: ...

    def error(self) -> None: ...


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


@dataclass
class _PerToolCounter:
    counts: dict[str, int] = field(default_factory=dict)


@dataclass
class ToolRepeatLimitToolset(WrapperToolset[AgentDepsT]):
    """Caps how often each distinct tool name may run within one run.

    Unlike CallBudgetToolset (which aborts the run), exceeding the limit does not
    end the run: it raises ModelRetry so the model is told to stop refetching and
    reason from the context it already gathered. Counts are tracked independently
    per tool name. Instantiate one per run so counts start fresh; the same instance
    must be reused for the whole run.
    """

    limit: int
    _counter: _PerToolCounter = field(default_factory=_PerToolCounter)

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: RunContext[AgentDepsT],
        tool: ToolsetTool[AgentDepsT],
    ) -> Any:
        if self._counter.counts.get(name, 0) >= self.limit:
            raise ModelRetry(
                f"{name} has already been called {self.limit} times, the maximum "
                f"for one run. Do not call {name} again; reason from the context "
                f"already gathered and produce the final answer."
            )
        self._counter.counts[name] = self._counter.counts.get(name, 0) + 1
        return await self.wrapped.call_tool(name, tool_args, ctx, tool)


@dataclass
class GlobalToolCounter:
    total: int = 0


@dataclass
class GlobalToolCallBudgetToolset(WrapperToolset[AgentDepsT]):
    """Nudges the model to conclude once cumulative tool calls cross a threshold.

    A single shared counter sums calls across every wrapped toolset, so the budget
    is global rather than per-server. Crossing the threshold does not end the run:
    it raises ModelRetry telling the model it has enough evidence and should emit
    its DiagnosisReport from what it has already gathered. The threshold sits below
    the hard request cap, so the model gets this hint while it still has budget to
    act on it. Pass one counter instance into every wrapper so the total is shared.
    """

    threshold: int
    counter: GlobalToolCounter = field(default_factory=GlobalToolCounter)

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: RunContext[AgentDepsT],
        tool: ToolsetTool[AgentDepsT],
    ) -> Any:
        if self.counter.total >= self.threshold:
            raise ModelRetry(
                f"{self.counter.total} tool calls made, enough evidence to conclude. "
                f"Stop gathering and emit the DiagnosisReport now from the context "
                f"already gathered."
            )
        self.counter.total += 1
        return await self.wrapped.call_tool(name, tool_args, ctx, tool)


@dataclass
class CircuitBreakerToolset(WrapperToolset[AgentDepsT]):
    """Drives a shared Breaker from hard MCP tool-call outcomes within one run.

    A successful call resets the run-wide consecutive count; a hard failure
    (transport error, MCP crash) counts toward the breaker threshold. The same
    instance must back every wrapped toolset so failures accumulate across stages.

    Wrap this on the outside of FilteredToolset/CallBudgetToolset so the breaker
    observes the delegated MCP outcome.
    """

    breaker: Breaker

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: RunContext[AgentDepsT],
        tool: ToolsetTool[AgentDepsT],
    ) -> Any:
        try:
            result = await self.wrapped.call_tool(name, tool_args, ctx, tool)
        except ModelRetry:
            raise
        except Exception:
            self.breaker.error()
            raise
        self.breaker.success()
        return result
