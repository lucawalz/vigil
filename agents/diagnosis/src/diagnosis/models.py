"""Typed contracts for the Diagnosis agent."""

from dataclasses import dataclass

from pydantic import BaseModel, Field
from pydantic_ai.mcp import MCPServerStdio


class DiagnosisReport(BaseModel):
    """8-field output from the Diagnosis agent."""

    root_cause: str = Field(description="One-sentence root cause, not a symptom")
    root_cause_component: str = Field(
        description="Deployment/pod/image name at fault (e.g., 'vigil-app:bad-tag-v9')"
    )
    severity: str = Field(pattern="^(low|medium|high|critical)$")
    affected_resources: list[str] = Field(
        description="Exact resource names from kubectl output, including namespace"
    )
    evidence: str = Field(description="Verbatim log line or event proving root cause")
    recommended_action: str = Field(
        pattern="^(apply_patch|rollout_undo|rebuild_nixos|escalate)$"
    )
    confidence: float = Field(ge=0.0, le=1.0)
    requires_os_level: bool


@dataclass(frozen=True)
class DiagnosisDeps:
    """kubectl + ssh + nixos scope only. No flux client."""

    kubectl_mcp: MCPServerStdio
    ssh_mcp: MCPServerStdio
    nixos_mcp: MCPServerStdio
