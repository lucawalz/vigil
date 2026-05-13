from __future__ import annotations

import os
from typing import TYPE_CHECKING

from common.provider import build_model
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.toolsets.filtered import FilteredToolset
from pydantic_ai.usage import Usage, UsageLimits

from .models import DiagnosisDeps, DiagnosisReport

if TYPE_CHECKING:
    from orchestrator.models import FaultEvent


_SYSTEM_PROMPT = """You are a Kubernetes SRE diagnosis agent operating on a K3s cluster.
Your only actions are tool calls using the tools listed below. Do not invent tool names.

Available tools:
  kubectl-mcp: get_nodes, get_pods, describe_pod, get_logs, rollout_status
  nixos-mcp:   get_journal, get_systemd_status, get_generations, rebuild_test

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
- If requires_os_level=False: use "apply_patch" for manifest drift, missing
  resources, or wrong field values; use "rollout_undo" only when a recent
  Deployment rollout is the direct cause and the previous revision is healthy.
- If requires_os_level=True: use "rebuild_nixos".
- requires_os_level and recommended_action must agree: never return "apply_patch"
  when requires_os_level=True, never return "rebuild_nixos" when
  requires_os_level=False.
- When confidence is below 0.6, gather more evidence with additional tool calls
  rather than committing to a repair action prematurely.

Do not call apply_patch, rollout_undo, switch_generation, or etcd_snapshot_save.
Those are remediation actions; diagnosis is read-only."""


diagnosis_agent: Agent[DiagnosisDeps, DiagnosisReport] = Agent(
    build_model(),
    deps_type=DiagnosisDeps,
    output_type=DiagnosisReport,
    retries=2,
    system_prompt=_SYSTEM_PROMPT,
)


async def run_diagnosis(
    deps: DiagnosisDeps,
    fault: FaultEvent,
    model: OpenAIChatModel | None = None,
) -> tuple[DiagnosisReport, Usage, list[ModelMessage]]:
    _nixos_write_tools = frozenset({"switch_generation", "etcd_snapshot_save"})
    _kubectl_write_tools = frozenset({"apply_patch", "rollout_undo"})
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
