"""Typed contracts for the Diagnosis agent."""

from dataclasses import dataclass
from typing import Any, Literal

from common.validators import coerce_null_sentinels
from pydantic import BaseModel, Field, model_validator
from pydantic_ai.mcp import MCPServerStdio
from pydantic_ai.messages import ModelMessage
from pydantic_ai.usage import RunUsage

_LIVE_ONLY = {"flux_reconcile", "nixos_rebuild"}
_DECLARED = {"git_commit_k8s", "git_commit_nix"}


class DiagnosisRequestBudgetExceeded(Exception):
    """Diagnosis exhausted its model-request budget before producing a report."""

    def __init__(self, usage: RunUsage, messages: list[ModelMessage]) -> None:
        super().__init__("diagnosis request budget exceeded")
        self.usage = usage
        self.messages = messages


class DiagnosisOutputRetryExhausted(Exception):
    """Diagnosis exhausted output-validation retries before producing a report.

    Carries the usage consumed by the failed attempts so the caller can record
    real token cost; a bare re-raise would drop it and report zero.
    """

    def __init__(
        self, usage: RunUsage, messages: list[ModelMessage], cause: Exception
    ) -> None:
        super().__init__(str(cause))
        self.usage = usage
        self.messages = messages


class DiagnosisReport(BaseModel):
    """Structured output from the Diagnosis agent."""

    root_cause: str = Field(description="One-sentence root cause, not a symptom")
    root_cause_component: str = Field(
        description="Deployment/pod/image at fault (e.g., '<deployment>:<bad-tag>')"
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
    resource_kind: str | None = Field(
        default=None,
        description="K8s resource kind (e.g. Deployment). Required for git_commit_k8s.",
    )
    resource_name: str | None = Field(
        default=None,
        description="Kubernetes resource name. Required for git_commit_k8s.",
    )
    resource_namespace: str | None = Field(
        default=None,
        description="Kubernetes resource namespace. Required for git_commit_k8s.",
    )
    patch_body: str | None = Field(
        default=None,
        description=(
            "Full replacement manifest YAML for git_commit_k8s and git_commit_nix;"
            " null for flux_reconcile / nixos_rebuild / escalate."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _coerce_null_sentinels(cls, data: Any) -> Any:
        return coerce_null_sentinels(cls, data)

    @model_validator(mode="after")
    def _drift_action_consistent(self) -> "DiagnosisReport":
        dc = self.drift_classification
        action = self.recommended_action
        if dc == "live_only_drift" and action not in _LIVE_ONLY:
            raise ValueError(
                f"Inconsistent: drift_classification='live_only_drift' with"
                f" recommended_action='{action}'. Either change"
                f" drift_classification to 'declared_drift' / 'both_drift' /"
                f" 'no_drift' to match the action, or change recommended_action"
                f" to 'flux_reconcile' / 'nixos_rebuild' to match the"
                f" classification. Re-examine the diff before deciding."
            )
        if dc == "declared_drift" and action not in _DECLARED:
            raise ValueError(
                f"Inconsistent: drift_classification='declared_drift' with"
                f" recommended_action='{action}'. Either change"
                f" drift_classification to 'live_only_drift' / 'both_drift' /"
                f" 'no_drift' to match the action, or change recommended_action"
                f" to 'git_commit_k8s' / 'git_commit_nix' to match the"
                f" classification. Re-examine the diff before deciding."
            )
        if dc in {"both_drift", "no_drift"} and action != "escalate":
            raise ValueError(
                f"Inconsistent: drift_classification='{dc}' with"
                f" recommended_action='{action}'. Either change"
                f" drift_classification to 'live_only_drift' or 'declared_drift'"
                f" to match the action, or change recommended_action to"
                f" 'escalate' to match the classification."
                f" Re-examine the diff before deciding."
            )
        return self

    @model_validator(mode="after")
    def _patch_fields_consistent(self) -> "DiagnosisReport":
        action = self.recommended_action
        has_any = any(
            f is not None
            for f in [
                self.resource_kind,
                self.resource_name,
                self.resource_namespace,
                self.patch_body,
            ]
        )
        if action not in {"git_commit_k8s", "git_commit_nix"} and has_any:
            raise ValueError(
                f"patch fields (resource_kind, resource_name, resource_namespace,"
                f" patch_body) must be null when recommended_action='{action}'."
            )
        return self


@dataclass(frozen=True)
class DiagnosisDeps:
    """Exposes kubectl-mcp, nixos-mcp, git-mcp, and flux-mcp to the diagnosis agent.

    git-mcp session is warmed via clone_repo before the LLM runs, so read_file
    is available for declared-state lookups. nixos-mcp is the typed NixOS
    interface for OS-layer observation. flux-mcp provides read access to
    Kustomization state.
    """

    kubectl_mcp: MCPServerStdio
    nixos_mcp: MCPServerStdio
    git_mcp: MCPServerStdio
    flux_mcp: MCPServerStdio
    run_id: str
