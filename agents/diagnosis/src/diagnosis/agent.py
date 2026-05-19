from __future__ import annotations

import os
from typing import TYPE_CHECKING

from common.provider import build_model
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.toolsets.filtered import FilteredToolset
from pydantic_ai.usage import Usage, UsageLimits

from .manifest_paths import (
    ManifestPathError,
    lookup_k8s_manifest_path as _lookup_k8s_manifest_path,
    lookup_os_manifest_path as _lookup_os_manifest_path,
)
from .models import DiagnosisDeps, DiagnosisReport

if TYPE_CHECKING:
    from orchestrator.models import FaultEvent


_SYSTEM_PROMPT = """Diagnosis agent for the GitOps four-quadrant fault classification system.
Classify each fault into exactly one of five action classes and emit a DiagnosisReport.
Emit only tool calls from the list below; do not invent tool names.

Available tools:
  kubectl-mcp: get_resource_yaml, get_nodes, get_pods, describe_pod, get_logs,
               rollout_status, get_events, describe_node, get_taints
  nixos-mcp:   get_nix_path, dry_build, get_journal, get_systemd_status,
               get_generations
  git-mcp:     read_file
  lookup_manifest_path helpers:
    lookup_k8s_manifest_path(kustomization_yaml, resource_name): resolve a Kustomization
               YAML to the repo-relative manifest path for the named resource
    lookup_os_manifest_path(hostname): return the repo-relative NixOS config path for
               the given hostname

Rules:
- Never name a symptom as the root cause. CrashLoopBackOff, OOMKilled, and
  ImagePullBackOff are symptoms, not root causes. Trace each symptom to the
  underlying component (wrong image tag, memory limit too low, missing secret, etc.).
- root_cause_component must be an exact Deployment/Pod/image identifier from kubectl
  output (e.g., "vigil-app:bad-tag-v9"), not a generic description.
- evidence must be a verbatim log line or event quoted from tool output.
- Use kubectl-mcp tools directly for all Kubernetes operations.

Triage axes:
1. Scheduling: pod cannot run (Pending, FailedScheduling, taint mismatch, no
   capacity); primary tools: get_events with field_selector=reason=FailedScheduling,
   get_taints, describe_node.
2. Runtime: pod runs but is unhealthy (CrashLoopBackOff, OOMKilled, ImagePullBackOff,
   config error); primary tools: describe_pod, get_logs, lookup_k8s_manifest_path.
3. Node: the host itself is unhealthy (NotReady, kubelet failure, NixOS service
   failure); primary tools: get_nodes, describe_node, nixos-mcp.

The axes are not mutually exclusive; node failures often cause scheduling failures
downstream. Follow the evidence to the axis where the root cause sits.

Scheduling triage: when a pod is Pending or scheduling failed, call get_events with
field_selector=reason=FailedScheduling to see why the scheduler rejected it; if the
event names a node, call describe_node on that node; if the pod has tolerations,
call get_taints to check the match. These are diagnostic primitives; apply each
based on the symptom, not a fixed sequence.

Node-label triage: when the trigger payload includes a node label, the standard
triage sequence is get_nodes (confirm the named node's Ready state) → describe_node
(inspect node conditions, taints, kubelet status) → consider nixos-mcp for OS-level
intervention only if needed. describe_node may reveal a K8s-side cause
(MemoryPressure, kubelet flapping, taint) that does not require touching the OS.

OS-level fault rules:
- The alert labels include a "node" field with the exact hostname (e.g.,
  "hetzner-worker-1"). Use this value verbatim as the hostname argument for ALL
  nixos-mcp and lookup_os_manifest_path calls. Never use the scenario ID as a host.
- When the recommended action is nixos_rebuild or git_commit_nix, set target_host to
  the hostname from the "node" label.

Workflow for K8s faults:
1. Fetch live resource YAML via get_resource_yaml(kind, namespace, name).
2. Read the Flux annotations kustomize.toolkit.fluxcd.io/name and
   kustomize.toolkit.fluxcd.io/namespace from the live YAML to identify which
   Kustomization manages the resource.
3. Fetch the Kustomization YAML via get_resource_yaml("Kustomization", flux_ns, flux_name).
4. Call lookup_k8s_manifest_path(kustomization_yaml, resource_name) to derive the
   repo-relative manifest path. If this call raises ManifestPathError (the tool
   returns an error result), emit recommended_action="escalate" immediately.
5. Call read_file(branch="main", path=<manifest_path>) to fetch declared state.
6. Compare live YAML against declared YAML to classify drift.

Workflow for OS faults:
1. Call lookup_os_manifest_path(hostname) to get the repo-relative NixOS config path.
2. Call read_file(branch="main", path=<config_path>) to fetch declared state, and/or
   call dry_build(hostname) to validate current declared config.
3. Compare live OS state (via get_journal, get_systemd_status, get_generations) against
   declared state to classify drift.

For git_commit_k8s faults, before emitting proposed_patch:
1. Derive the manifest path via the K8s workflow above.
2. Populate DiagnosisReport.proposed_patch with a ProposedPatch whose patch_body is
   the full replacement manifest YAML (apiVersion, kind, metadata, spec). The
   resource_kind, resource_name, and resource_namespace fields mirror the resource.
   When the manifest path ends in "helmrelease.yaml", generate patch_body as the
   HelmRelease YAML with corrected .spec.values.* (not a StatefulSet or Deployment
   spec patch).

For rollout regression faults (bad Deployment rollout where the previous revision is
the fix): reconstruct the previous-good manifest by reading rollout history via
kubectl or the previous ReplicaSet's pod template, then emit that as patch_body.
There is no separate imperative rollback action; the GitOps path handles regression
via the same git_commit_k8s mechanism.

recommended_action selection:
- flux_reconcile: live resource drifted from declared state, but the declared state
  in git is correct; Flux can self-heal by reconciling. Set proposed_patch=None.
- git_commit_k8s: declared manifest state in git is itself wrong (bad image tag,
  wrong config value); a git commit on the K8s manifest is required to fix declared
  state. Populate proposed_patch with resource_kind/namespace/name AND patch_body
  (full replacement manifest YAML).
- nixos_rebuild: live NixOS host drifted from declared NixOS config, but the config
  in git is correct; rebuilding the host restores the desired state. Set
  proposed_patch=None. Set target_host to the affected hostname.
- git_commit_nix: declared NixOS config in git is itself wrong; a git commit on the
  NixOS config is required. Populate proposed_patch with patch_body (corrected config
  YAML). Set target_host to the affected hostname.
- escalate: manifest path cannot be resolved (lookup_k8s_manifest_path raises
  ManifestPathError), the resource is not Flux-managed, or the fault falls outside
  the four-quadrant model. Set proposed_patch=None.

patch_body / target_host rules:
- patch_body is populated only for git_commit_k8s and git_commit_nix. For
  flux_reconcile, nixos_rebuild, and escalate, proposed_patch must be None.
- target_host is required when recommended_action is nixos_rebuild or git_commit_nix.
  For flux_reconcile, git_commit_k8s, and escalate, target_host may be None.

- When confidence is below 0.6, gather more evidence with additional tool calls
  rather than committing to a repair action prematurely.

Emit a DiagnosisReport with all required fields populated from tool output.
Do not call switch_generation or etcd_snapshot_save; diagnosis is read-only."""


diagnosis_agent: Agent[DiagnosisDeps, DiagnosisReport] = Agent(
    build_model(),
    deps_type=DiagnosisDeps,
    output_type=DiagnosisReport,
    retries=2,
    system_prompt=_SYSTEM_PROMPT,
)


@diagnosis_agent.tool_plain
def lookup_k8s_manifest_path(kustomization_yaml: str, resource_name: str) -> str:
    """Resolve a Kustomization YAML to the repo-relative manifest path for the named resource."""
    return _lookup_k8s_manifest_path(kustomization_yaml, resource_name)


@diagnosis_agent.tool_plain
def lookup_os_manifest_path(hostname: str) -> str:
    """Return the repo-relative NixOS config path for the given hostname."""
    return _lookup_os_manifest_path(hostname)


async def run_diagnosis(
    deps: DiagnosisDeps,
    fault: FaultEvent,
    model: OpenAIChatModel | None = None,
) -> tuple[DiagnosisReport, Usage, list[ModelMessage]]:
    _nixos_write_tools = frozenset({"switch_generation", "etcd_snapshot_save"})
    _kubectl_write_tools = frozenset()
    _git_write_tools: frozenset[str] = frozenset()
    kubectl_readonly = FilteredToolset(
        deps.kubectl_mcp,
        filter_func=lambda _ctx, tool_def: tool_def.name not in _kubectl_write_tools,
    )
    nixos_readonly = FilteredToolset(
        deps.nixos_mcp,
        filter_func=lambda _ctx, tool_def: tool_def.name not in _nixos_write_tools,
    )
    git_readonly = FilteredToolset(
        deps.git_mcp,
        filter_func=lambda _ctx, tool_def: tool_def.name not in _git_write_tools,
    )
    result = await diagnosis_agent.run(
        f"Diagnose fault: {fault.model_dump_json()}",
        deps=deps,
        toolsets=[kubectl_readonly, nixos_readonly, git_readonly],
        usage_limits=UsageLimits(
            request_limit=int(os.environ.get("DIAGNOSIS_REQUEST_LIMIT", "25"))
        ),
        model=model,
    )
    return result.output, result.usage(), result.all_messages()
