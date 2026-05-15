"""Typed contracts for the Remediation agent."""

from dataclasses import dataclass

from pydantic import BaseModel
from pydantic_ai.mcp import MCPServerStdio


class RemediationResult(BaseModel):
    """Remediation agent output.

    destructive_repair flags whether any mutation tool was called.
    merge_commit_sha, agent_branch, agent_commits, and gate_status are
    populated from wait_for_gate and create_branch returns on the K8s path.
    """

    success: bool
    actions_taken: list[str]
    tool_calls_count: int
    destructive_repair: bool
    merge_commit_sha: str | None = None
    agent_branch: str | None = None
    agent_commits: list[str] | None = None
    gate_status: str | None = None


@dataclass(frozen=True)
class RemediationDeps:
    """git + flux + nixos scope only. No kubectl client; reads happen at diagnosis time."""

    git_mcp: MCPServerStdio
    flux_mcp: MCPServerStdio
    nixos_mcp: MCPServerStdio
