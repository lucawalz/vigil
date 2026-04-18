"""Typed contracts for the Remediation agent."""

from dataclasses import dataclass

from pydantic import BaseModel
from pydantic_ai.mcp import MCPServerStdio


class RemediationResult(BaseModel):
    """Remediation agent output.

    destructive_repair flags whether any mutation tool was called.
    """

    success: bool
    actions_taken: list[str]
    tool_calls_count: int
    destructive_repair: bool


@dataclass(frozen=True)
class RemediationDeps:
    """kubectl + flux + nixos scope only. No ssh client."""

    kubectl_mcp: MCPServerStdio
    flux_mcp: MCPServerStdio
    nixos_mcp: MCPServerStdio
