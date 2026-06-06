"""Typed contracts for the Watchdog agent."""

from dataclasses import dataclass

from common.constants import WATCHDOG_NAMESPACE
from pydantic import BaseModel
from pydantic_ai.mcp import MCPServerStdio

_DEFAULT_FLUX_KUSTOMIZATION_NAME = "cluster-apps"
_DEFAULT_FLUX_KUSTOMIZATION_NAMESPACE = "flux-system"


class HealthSnapshotUnavailable(RuntimeError):
    """Health could not be determined from a tool response.

    Raised when pod counts cannot be parsed from an unrecognised tool-output
    shape, so callers treat the read as indeterminate rather than as zero
    ready pods.
    """


class HealthSnapshot(BaseModel):
    """Absolute workload + namespace + Flux health at one poll iteration."""

    workload_found: bool = False
    generation: int | None = None
    observed_generation: int | None = None
    spec_replicas: int | None = None
    ready_replicas: int | None = None
    updated_replicas: int | None = None
    available_replicas: int | None = None
    available_condition: bool | None = None
    progressing_ok: bool | None = None
    progress_deadline_exceeded: bool = False
    ready_pods: int = 0
    total_pods: int = 0
    flux_ready: bool | None = None
    flux_revision: str | None = None
    captured_at: str


class WatchdogResult(BaseModel):
    """Watchdog observes; Orchestrator decides rollback."""

    degraded: bool
    snapshot: HealthSnapshot | None = None
    reason: str | None = None


@dataclass(frozen=True)
class WatchdogDeps:
    """kubectl and flux-mcp read scope plus the remediation target identity."""

    kubectl_mcp: MCPServerStdio
    flux_mcp: MCPServerStdio
    namespace: str = WATCHDOG_NAMESPACE
    target_kind: str | None = None
    target_name: str | None = None
    expected_revision: str | None = None
    flux_kustomization_name: str = _DEFAULT_FLUX_KUSTOMIZATION_NAME
    flux_kustomization_namespace: str = _DEFAULT_FLUX_KUSTOMIZATION_NAMESPACE
    nixos_mcp: MCPServerStdio | None = None
    target_host: str | None = None
    os_check_kind: str | None = None
    os_check_key: str | None = None
    os_check_expected: str | None = None
