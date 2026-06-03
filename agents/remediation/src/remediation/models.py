"""Typed contracts for the Remediation agent."""

from dataclasses import dataclass

from pydantic import BaseModel
from pydantic_ai.mcp import MCPServerStdio


class GitCommitBudgetExceeded(Exception):
    """Raised when a run exceeds its allotted commit_files invocations."""


class RemediationResult(BaseModel):
    """Remediation agent output.

    mutation_attempted flags whether any mutation tool was called. It is the
    raw signal; the orchestrator derives the run-level destructive_repair safety
    metric from it together with the final watchdog and rollback outcomes.
    merge_commit_sha, agent_branch, agent_commits, and gate_status are
    populated from wait_for_gate and create_branch returns on the K8s path.
    """

    success: bool
    actions_taken: list[str]
    tool_calls_count: int
    mutation_attempted: bool
    merge_commit_sha: str | None = None
    agent_branch: str | None = None
    agent_commits: list[str] | None = None
    gate_status: str | None = None


@dataclass(frozen=True)
class RemediationDeps:
    """git + flux + nixos scope only. No kubectl client; reads at diagnosis time."""

    git_mcp: MCPServerStdio
    flux_mcp: MCPServerStdio
    nixos_mcp: MCPServerStdio
