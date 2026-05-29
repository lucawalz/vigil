from __future__ import annotations

import os
from typing import TYPE_CHECKING

from common import trace
from common.constants import (
    DIAGNOSIS_FLUX_READ_TOOLS,
    DIAGNOSIS_GIT_READ_TOOLS,
    DIAGNOSIS_KUBECTL_READ_TOOLS,
    DIAGNOSIS_NIXOS_READ_TOOLS,
)
from common.provider import build_model
from pydantic_ai import Agent
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.toolsets.filtered import FilteredToolset
from pydantic_ai.usage import Usage, UsageLimits

from .context import DiagnosisContext
from .manifest_paths import lookup_os_manifest_path as _lookup_os_manifest_path
from .models import DiagnosisDeps, DiagnosisReport

if TYPE_CHECKING:
    from orchestrator.models import FaultEvent
    from pydantic_ai.mcp import MCPServerStdio


_SYSTEM_PROMPT = """GitOps four-quadrant fault classification agent.
Classify each fault into exactly one of five action classes and emit a DiagnosisReport.
Emit only tool calls from the list below; do not invent tool names.

Available tools:
  kubectl-mcp: get_resource_yaml, get_nodes, get_pods, describe_pod, get_logs,
               rollout_status, get_events, describe_node, get_taints
  nixos-mcp:   get_nix_path, dry_build, get_journal, get_systemd_status,
               get_generations
  git-mcp:     clone_repo, read_file, resolve_manifest_path
  flux-mcp:    get_kustomization_status, get_gitrepository_status
  lookup_manifest_path helpers:
    lookup_os_manifest_path(hostname): return the repo-relative NixOS config path for
               the given hostname

Ground-truth context (DiagnosisContext):
The user message includes a DiagnosisContext block containing:
  source_branch, manifest_path, live_yaml, declared_yaml, diff,
  live_pod_status, live_admission_objects
These fields are pre-computed by Python and are ground truth. Treat them as
authoritative inputs. Do not call get_resource_yaml to re-derive live_yaml; that
call has already been made. Use the provided diff to determine drift direction.
live_pod_status: pre-fetched pod and event table for the alert's namespace.
  Non-empty for K8s workload alerts. Contains pod phase/readiness and recent
  namespace events. Use this as primary pod-failure evidence before calling
  additional kubectl tools.
live_admission_objects: list of ResourceQuota/LimitRange/NetworkPolicy objects
  discovered in the alert's namespace, each annotated with declared_in_git (True/False)
  and git_path. An object with declared_in_git=False is an out-of-band live injection.
  For such objects: set drift_classification=live_only_drift only if an agent tool can
  remove them; otherwise escalate.
The git-mcp session is pre-warmed; use read_file(branch, path) to inspect related
manifests (parent Kustomizations, ConfigMap sources, Helm values) when needed.
If read_file returns a path-not-found error for manifest_path, call
resolve_manifest_path(kustomize_path, kind, name, namespace) with the
Kustomization spec.path to recover the correct path, then retry read_file once.
If that also fails, set recommended_action=escalate.

Rules:
- Never name a symptom as the root cause. CrashLoopBackOff, OOMKilled, and
  ImagePullBackOff are symptoms, not root causes. Trace each symptom to the
  underlying component (wrong image tag, memory limit too low, missing secret, etc.).
- root_cause_component must be an exact Deployment/Pod/image identifier from kubectl
  output (e.g., "Deployment/vigil-app"), not a generic description.
- evidence must be a verbatim log line or event quoted from tool output.
- Use kubectl-mcp tools for follow-up investigation (events, logs, taints, node
  status) as needed.

Triage axes:
1. Scheduling: pod cannot run (Pending, FailedScheduling, taint mismatch, no
   capacity); primary tools: get_events with field_selector=reason=FailedScheduling,
   get_taints, describe_node.
2. Runtime: pod runs but is unhealthy (CrashLoopBackOff, OOMKilled, ImagePullBackOff,
   config error); primary tools: describe_pod, get_logs, get_resource_yaml.
3. Node: the host itself is unhealthy (NotReady, kubelet failure, NixOS service
   failure); primary tools: get_nodes, describe_node, nixos-mcp.
4. Admission control: namespace-scoped objects (ResourceQuota, LimitRange,
   NetworkPolicy) can block or throttle workloads independently of the workload
   manifest. Check live_admission_objects in DiagnosisContext first - objects with
   declared_in_git=False are out-of-band live injections not present in git. If any
   such blocking object is present and no agent tool can remove it, escalate. If
   live_admission_objects is empty but live_pod_status shows Pending or FailedCreate
   events, call get_events for the namespace to look for quota or scheduling messages.

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

Flux-layer triage: when the alert labels include `kustomization`, live_yaml contains
the Kustomization status output (pre-fetched). Read the apply error message in
live_yaml verbatim - it names the rejected field and the affected resource. Then
call git_mcp.read_file(source_branch, path) on the manifest indicated by the error
to verify the declared value. Derive manifest_path from the Kustomization spec.path
and the failing resource name (DiagnosisContext.manifest_path is null for Kustomization
alerts - do not rely on it). Set drift_classification=declared_drift and
recommended_action=git_commit_k8s when the declared manifest contains the wrong value.

OS-level fault rules:
- The alert labels include a "node" field with the exact hostname (e.g.,
  "hetzner-worker-1"). Use this value verbatim as the hostname argument for ALL
  nixos-mcp and lookup_os_manifest_path calls. Never use the scenario ID as a host.
- When the recommended action is nixos_rebuild or git_commit_nix, set target_host to
  the hostname from the "node" label.

Drift classification from DiagnosisContext:
Use the provided diff field from DiagnosisContext to classify drift direction.
Metadata-noise filter: when reading the diff, ignore lines whose paths fall under
  metadata.creationTimestamp, metadata.generation, metadata.resourceVersion,
  metadata.uid, metadata.managedFields, status.*, or
  metadata.annotations['kubectl.kubernetes.io/last-applied-configuration'].
  These are runtime-only fields and do not represent meaningful drift.
  live_only_drift: live_yaml differs from declared_yaml because the cluster mutated
    but git is correct. The non-metadata diff shows lines present in live but absent
    in declared.
  declared_drift: declared_yaml itself has the wrong value; git must be fixed. Either
    (a) the non-metadata diff shows lines in declared that contradict the live state,
    OR (b) live and declared agree but both contain a value contradicted by the alert
    signal or live_pod_status events. In case (b), reason from declared_yaml's contents
    against the failure mode, not from the diff.
  both_drift: live and declared both deviate from the expected state; escalate.
  no_drift: live_yaml and declared_yaml are identical (excluding runtime metadata
    noise). Classify as no_drift only when: (i) the non-metadata diff is empty AND
    (ii) live_pod_status shows no unhealthy pods AND live_admission_objects shows
    nothing out-of-band AND the named resource is in a healthy state. If the alert
    claims a fault but all cluster indicators look healthy, set
    recommended_action=escalate. If live_pod_status shows unhealthy pods while the
    diff is clean, investigate further - do not choose no_drift until you have
    exhausted live_pod_status and live_admission_objects as evidence sources.

For git_commit_k8s faults, before emitting patch fields:
1. Use DiagnosisContext.manifest_path as the target path (do not re-derive it).
2. Populate DiagnosisReport.patch_body with the corrected manifest YAML derived from
   DiagnosisContext.declared_yaml with the single faulty field corrected.
   Never use get_resource_yaml output as the base for patch_body — it contains
   runtime-only fields (creationTimestamp, resourceVersion, uid, status) that must
   not enter git. Set resource_kind, resource_name, and resource_namespace to mirror
   the affected resource. When the manifest path ends in "helmrelease.yaml", generate
   patch_body as the HelmRelease YAML with corrected .spec.values.* (not a
   StatefulSet or Deployment spec patch).

For rollout regression faults (bad Deployment rollout where the previous revision is
the fix): reconstruct the previous-good manifest by reading rollout history via
kubectl or the previous ReplicaSet's pod template, then emit that as patch_body.
There is no separate imperative rollback action; the GitOps path handles regression
via the same git_commit_k8s mechanism.

Drift-to-action mapping (drift_classification drives recommended_action):
- live_only_drift → flux_reconcile (K8s) or nixos_rebuild (OS). Git is correct.
- declared_drift → git_commit_k8s (K8s) or git_commit_nix (OS). Git must be fixed.
- both_drift / no_drift → escalate. The situation is outside the four-quadrant model.
These mappings are enforced by the DiagnosisReport schema validator. If you hit a
validator error, do not assume the action is the field to change - re-examine which
field is actually wrong given the evidence.

recommended_action selection:
- flux_reconcile: live resource drifted from declared state, but the declared state
  in git is correct; Flux can self-heal by reconciling. Set all patch fields to null.
- git_commit_k8s: declared manifest state in git is itself wrong (bad image tag,
  wrong config value); a git commit on the K8s manifest is required to fix declared
  state. Populate resource_kind, resource_name, resource_namespace, and patch_body
  (full replacement manifest YAML derived from DiagnosisContext.declared_yaml, not
  from live YAML).
- nixos_rebuild: live NixOS host drifted from declared NixOS config, but the config
  in git is correct; rebuilding the host restores the desired state. Set all patch
  fields to null. Set target_host to the affected hostname.
- git_commit_nix: declared NixOS config in git is itself wrong; a git commit on the
  NixOS config is required. Populate patch_body (corrected config YAML derived from
  DiagnosisContext.declared_yaml). Set target_host to the affected hostname.
- escalate: resolve_manifest_path could not locate the manifest, the resource is not
  Flux-managed, or the fault falls outside
  the four-quadrant model. Set all patch fields to null.

patch_body / target_host rules:
- patch_body is populated only for git_commit_k8s and git_commit_nix. For
  flux_reconcile, nixos_rebuild, and escalate, all patch fields must be null.
- target_host is required when recommended_action is nixos_rebuild or git_commit_nix.
  For flux_reconcile, git_commit_k8s, and escalate, target_host may be null.

- When confidence is below 0.6, gather more evidence with additional tool calls
  rather than committing to a repair action prematurely.

Emit a DiagnosisReport with all required fields populated from tool output and the
provided DiagnosisContext.
Do not call switch_generation or etcd_snapshot_save; diagnosis is read-only."""


diagnosis_agent: Agent[DiagnosisDeps, DiagnosisReport] = Agent(
    build_model(),
    deps_type=DiagnosisDeps,
    output_type=DiagnosisReport,
    retries=2,
    system_prompt=_SYSTEM_PROMPT,
)


@diagnosis_agent.tool_plain
def lookup_os_manifest_path(hostname: str) -> str:
    """Return the repo-relative NixOS config path for the given hostname."""
    return _lookup_os_manifest_path(hostname)


def _build_user_message(
    fault: "FaultEvent",
    context: DiagnosisContext,
    retry_hint: str | None = None,
) -> str:
    admission_lines: list[str] = []
    for ao in context.live_admission_objects:
        in_git = "in-git" if ao.declared_in_git else "NOT-in-git"
        line = f"    {ao.kind}/{ao.name} ({ao.namespace}) [{in_git}]"
        if ao.git_path:
            line += f" git_path={ao.git_path}"
        line += f"\n      {ao.summary}"
        admission_lines.append(line)
    admission_block = (
        "  live_admission_objects:\n" + "\n".join(admission_lines)
        if admission_lines
        else "  live_admission_objects: []"
    )
    retry_block = f"Retry signal: {retry_hint}\n\n" if retry_hint else ""
    return (
        f"{retry_block}"
        f"Diagnose fault.\n\n"
        f"Fault: {fault.model_dump_json()}\n\n"
        f"DiagnosisContext:\n"
        f"  source_branch: {context.source_branch}\n"
        f"  manifest_path: {context.manifest_path}\n"
        f"  live_yaml:\n{context.live_yaml}\n"
        f"  declared_yaml:\n{context.declared_yaml}\n"
        f"  diff:\n{context.diff}\n"
        f"  live_pod_status:\n{context.live_pod_status}\n"
        f"{admission_block}"
    )


def is_diagnosis_tool_allowed(
    tool_name: str,
    allowed_tools: frozenset[str],
    blocked_tools: frozenset[str],
) -> bool:
    return tool_name in allowed_tools and tool_name not in blocked_tools


def _build_readonly_toolset(
    server: MCPServerStdio,
    allowed_tools: frozenset[str],
    blocked_tools: frozenset[str],
) -> FilteredToolset:
    return FilteredToolset(
        server,
        filter_func=lambda _ctx, tool_def: is_diagnosis_tool_allowed(
            tool_def.name, allowed_tools, blocked_tools
        ),
    )


async def run_diagnosis(
    deps: DiagnosisDeps,
    fault: FaultEvent,
    context: DiagnosisContext,
    model: OpenAIChatModel | None = None,
    blocked_tools: frozenset[str] = frozenset(),
    retry_hint: str | None = None,
) -> tuple[DiagnosisReport, Usage, list[ModelMessage]]:
    kubectl_readonly = _build_readonly_toolset(
        deps.kubectl_mcp, DIAGNOSIS_KUBECTL_READ_TOOLS, blocked_tools
    )
    nixos_readonly = _build_readonly_toolset(
        deps.nixos_mcp, DIAGNOSIS_NIXOS_READ_TOOLS, blocked_tools
    )
    git_readonly = _build_readonly_toolset(
        deps.git_mcp, DIAGNOSIS_GIT_READ_TOOLS, blocked_tools
    )
    flux_readonly = _build_readonly_toolset(
        deps.flux_mcp, DIAGNOSIS_FLUX_READ_TOOLS, blocked_tools
    )
    constraint_block = ""
    if blocked_tools:
        constraint_block = (
            f"\n\nScenario constraint: these tools are unavailable for this run: "
            f"{', '.join(sorted(blocked_tools))}. "
            f"If your recommended action requires one of these tools, "
            f"set recommended_action=escalate."
        )
    user_message = _build_user_message(fault, context, retry_hint) + constraint_block
    async with diagnosis_agent.iter(
        user_message,
        deps=deps,
        toolsets=[kubectl_readonly, nixos_readonly, git_readonly, flux_readonly],
        usage_limits=UsageLimits(
            request_limit=int(os.environ.get("DIAGNOSIS_REQUEST_LIMIT", "25"))
        ),
        model=model,
    ) as agent_run:
        try:
            async for _ in agent_run:
                pass
        except UnexpectedModelBehavior:
            partial_msgs = agent_run.all_messages()
            if partial_msgs:
                trace.write_trace(deps.run_id, "diagnosis", partial_msgs, partial=True)
            raise
    return agent_run.result.output, agent_run.usage, agent_run.all_messages()
