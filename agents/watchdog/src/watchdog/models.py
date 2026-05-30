"""Typed contracts for the Watchdog agent."""

from dataclasses import dataclass

from common.constants import WATCHDOG_NAMESPACE
from pydantic import BaseModel
from pydantic_ai.mcp import MCPServerStdio


class HealthSnapshotUnavailable(RuntimeError):
    """Health could not be determined from a tool response.

    Raised when pod counts cannot be parsed from an unrecognised tool-output
    shape, so callers treat the read as indeterminate rather than as zero
    ready pods.
    """


class HealthSnapshot(BaseModel):
    """Pre-remediation baseline + each poll iteration."""

    ready_pods: int
    total_pods: int
    endpoints_healthy: bool
    flux_ready: bool | None = None
    captured_at: str


class WatchdogResult(BaseModel):
    """Watchdog observes; Orchestrator decides rollback."""

    degraded: bool
    snapshot: HealthSnapshot | None = None


@dataclass(frozen=True)
class WatchdogDeps:
    """kubectl and flux-mcp read scope."""

    kubectl_mcp: MCPServerStdio
    flux_mcp: MCPServerStdio
    namespace: str = WATCHDOG_NAMESPACE
