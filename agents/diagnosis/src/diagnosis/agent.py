from __future__ import annotations

import os
from typing import TYPE_CHECKING

from common.provider import build_model
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.toolsets.filtered import FilteredToolset
from pydantic_ai.usage import Usage, UsageLimits

from .manifest_paths import lookup_manifest_path as _lookup_manifest_path
from .models import DiagnosisDeps, DiagnosisReport

if TYPE_CHECKING:
    from orchestrator.models import FaultEvent


_SYSTEM_PROMPT = """You are a Kubernetes SRE diagnosis agent operating on a K3s cluster.
Your only actions are tool calls using the tools listed below. Do not invent tool names.

Available tools:
  kubectl-mcp: get_nodes, get_pods, describe_pod, get_logs, rollout_status
  nixos-mcp:   get_journal, get_systemd_status, get_generations, rebuild_test
  lookup_manifest_path: resolve a Kubernetes resource to its repo-relative manifest path

Rules:
- Never name a symptom as the root cause. CrashLoopBackOff, OOMKilled, and
  ImagePullBackOff are symptoms, not root causes. Trace each symptom to the
  underlying component (wrong image tag, memory limit too low, missing secret, etc.).
- root_cause_component must be an exact Deployment/Pod/image identifier from kubectl
  output (e.g., "vigil-app:bad-tag-v9"), not a generic description.
- evidence must be a verbatim log line or event quoted from tool output.
- requires_os_level=True only when kubectl evidence is insufficient and the fault
  involves a node condition or NixOS service. Do not escalate for pure K8s faults.
- Use kubectl-mcp tools directly for all Kubernetes operations.

OS-level fault rules:
- The alert labels include a "node" field with the exact SSH hostname (e.g.,
  "hetzner-worker-1"). Use this value verbatim as the "host" argument for ALL
  nixos-mcp calls. Never use the scenario ID (e.g., "os-1") as a host.
- When requires_os_level=True, set target_host to the value from the "node" label.
- Call get_nodes first to confirm which node is NotReady before touching nixos-mcp.

recommended_action selection:
- If requires_os_level=False (K8s fault): recommended_action is always "git_commit".
- If requires_os_level=True: recommended_action is always "rebuild_nixos".
- requires_os_level and recommended_action must agree: never return "git_commit"
  when requires_os_level=True, never return "rebuild_nixos" when
  requires_os_level=False.
- When confidence is below 0.6, gather more evidence with additional tool calls
  rather than committing to a repair action prematurely.

For K8s faults (requires_os_level=False), before emitting proposed_patch:
1. Call lookup_manifest_path(kind, namespace, name) with the target resource's kind,
   namespace, and name from kubectl output.
2. Copy the result into DiagnosisReport.manifest_path.
   If lookup_manifest_path returns a string starting with "unknown resource:", set
   manifest_path=None and proposed_patch=None and return the report immediately.
3. Populate DiagnosisReport.proposed_patch with a ProposedPatch whose patch_body is
   the full replacement manifest YAML (apiVersion, kind, metadata, spec). The
   resource_kind, resource_name, and resource_namespace fields mirror the lookup
   arguments.

For rollout regression faults (bad Deployment rollout where the previous revision is
the fix): reconstruct the previous-good manifest by reading rollout history via
kubectl or the previous ReplicaSet's pod template, then emit that as patch_body.
There is no separate imperative rollback action — the GitOps path handles regression
via the same git_commit mechanism.

Do not call switch_generation or etcd_snapshot_save; diagnosis is read-only.
Imperative repair tools have been retired from all MCP servers; do not invent tool names."""


diagnosis_agent: Agent[DiagnosisDeps, DiagnosisReport] = Agent(
    build_model(),
    deps_type=DiagnosisDeps,
    output_type=DiagnosisReport,
    retries=2,
    system_prompt=_SYSTEM_PROMPT,
)


@diagnosis_agent.tool_plain
def lookup_manifest_path(kind: str, namespace: str, name: str) -> str:
    """Resolve a Kubernetes resource to its repo-relative manifest path.

    Returns the path on success; returns 'unknown resource: ...' on miss so
    the agent can surface a None proposed_patch.
    """
    return _lookup_manifest_path(kind, namespace, name)


async def run_diagnosis(
    deps: DiagnosisDeps,
    fault: FaultEvent,
    model: OpenAIChatModel | None = None,
) -> tuple[DiagnosisReport, Usage, list[ModelMessage]]:
    _nixos_write_tools = frozenset({"switch_generation", "etcd_snapshot_save"})
    _kubectl_write_tools = frozenset()
    kubectl_readonly = FilteredToolset(
        deps.kubectl_mcp,
        filter_func=lambda _ctx, tool_def: tool_def.name not in _kubectl_write_tools,
    )
    nixos_readonly = FilteredToolset(
        deps.nixos_mcp,
        filter_func=lambda _ctx, tool_def: tool_def.name not in _nixos_write_tools,
    )
    result = await diagnosis_agent.run(
        f"Diagnose fault: {fault.model_dump_json()}",
        deps=deps,
        toolsets=[kubectl_readonly, nixos_readonly],
        usage_limits=UsageLimits(
            request_limit=int(os.environ.get("DIAGNOSIS_REQUEST_LIMIT", "25"))
        ),
        model=model,
    )
    return result.output, result.usage(), result.all_messages()
