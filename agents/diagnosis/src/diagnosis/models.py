"""Typed contracts for the Diagnosis agent."""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field, model_validator
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


_LIVE_ONLY = {"flux_reconcile", "nixos_rebuild"}
_DECLARED = {"git_commit_k8s", "git_commit_nix"}


class DiagnosisReport(BaseModel):
    """Structured output from the Diagnosis agent."""

    root_cause: str = Field(description="One-sentence root cause, not a symptom")
    root_cause_component: str = Field(
        description="Deployment/pod/image name at fault (e.g., '<deployment>:<bad-tag>')"
    )
    severity: str = Field(pattern="^(low|medium|high|critical)$")
    affected_resources: list[str] = Field(
        description="Exact resource names from kubectl output, including namespace"
    )
    evidence: str = Field(description="Verbatim log line or event proving root cause")
    drift_classification: Literal[
        "live_only_drift",
        "declared_drift",
        "both_drift",
        "no_drift",
    ] = Field(
        description=(
            "Direction of drift. live_only_drift: cluster mutated, git is correct."
            " declared_drift: git itself has the wrong value."
            " both_drift or no_drift: escalate."
        )
    )
    recommended_action: Literal[
        "flux_reconcile",
        "git_commit_k8s",
        "nixos_rebuild",
        "git_commit_nix",
        "escalate",
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

    @model_validator(mode="after")
    def _drift_action_consistent(self) -> "DiagnosisReport":
        dc = self.drift_classification
        action = self.recommended_action
        if dc == "live_only_drift" and action not in _LIVE_ONLY:
            raise ValueError(
                f"drift_classification='live_only_drift' requires flux_reconcile or"
                f" nixos_rebuild, not '{action}'"
            )
        if dc == "declared_drift" and action not in _DECLARED:
            raise ValueError(
                f"drift_classification='declared_drift' requires git_commit_k8s or"
                f" git_commit_nix, not '{action}'"
            )
        if dc in {"both_drift", "no_drift"} and action != "escalate":
            raise ValueError(
                f"drift_classification='{dc}' requires escalate, not '{action}'"
            )
        return self


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
