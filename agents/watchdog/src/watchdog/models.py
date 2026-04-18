"""Typed contracts for the Watchdog agent."""

from dataclasses import dataclass

from pydantic import BaseModel
from pydantic_ai.mcp import MCPServerStdio


class HealthSnapshot(BaseModel):
    """Pre-remediation baseline + each poll iteration."""

    ready_pods: int
    total_pods: int
    endpoints_healthy: bool
    captured_at: str


class WatchdogResult(BaseModel):
    """Watchdog observes; Orchestrator decides rollback."""

    degraded: bool
    snapshot: HealthSnapshot | None = None


@dataclass(frozen=True)
class WatchdogDeps:
    """kubectl scope only."""

    kubectl_mcp: MCPServerStdio
