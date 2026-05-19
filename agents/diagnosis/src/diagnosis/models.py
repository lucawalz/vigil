"""Typed contracts for the Diagnosis agent."""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_ai.mcp import MCPServerStdio


class ProposedPatch(BaseModel):
    resource_kind: str
    resource_name: str
    resource_namespace: str
    patch_body: str | None = Field(
        default=None,
        description=(
            "Full replacement manifest YAML for git_commit_k8s and git_commit_nix;"
            " None for flux_reconcile / nixos_rebuild / escalate."
        ),
    )


class DiagnosisReport(BaseModel):
    """Structured output from the Diagnosis agent."""

    root_cause: str = Field(description="One-sentence root cause, not a symptom")
    root_cause_component: str = Field(
        description="Deployment/pod/image name at fault (e.g., 'vigil-app:bad-tag-v9')"
    )
    severity: str = Field(pattern="^(low|medium|high|critical)$")
    affected_resources: list[str] = Field(
        description="Exact resource names from kubectl output, including namespace"
    )
    evidence: str = Field(description="Verbatim log line or event proving root cause")
    recommended_action: Literal[
        "flux_reconcile", "git_commit_k8s", "nixos_rebuild",
        "git_commit_nix", "escalate"
    ]
    confidence: float = Field(ge=0.0, le=1.0)
    target_host: str | None = Field(
        default=None,
        description=(
            "NixOS hostname for OS tools."
            " Required when recommended_action is 'nixos_rebuild' or 'git_commit_nix'."
        ),
    )
    manifest_path: str | None = Field(
        default=None,
        description=(
            "Repo-relative path to the manifest file the patch_body should overwrite"
        ),
    )
    proposed_patch: ProposedPatch | None = Field(
        default=None,
        description=(
            "Full replacement manifest YAML and resource identifiers"
            " for git-mcp.write_manifest"
        ),
    )


@dataclass(frozen=True)
class DiagnosisDeps:
    """Exposes kubectl-mcp, nixos-mcp, and git-mcp to the diagnosis agent.

    git-mcp provides declared-state reads via read_file for Kustomization YAML
    lookup. nixos-mcp is the typed NixOS interface for OS-layer remediation.
    ssh-mcp is intentionally excluded — it duplicates nixos-mcp's SSH-backed tools.
    """

    kubectl_mcp: MCPServerStdio
    nixos_mcp: MCPServerStdio
    git_mcp: MCPServerStdio
