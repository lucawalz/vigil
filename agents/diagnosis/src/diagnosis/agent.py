"""Diagnosis agent: ReAct loop over kubectl/nixos MCP tools.

Emits a structured DiagnosisReport per run.
Tool scope: kubectl-mcp and nixos-mcp only; ssh-mcp is excluded to prevent the
model from confusing run_allowed_command with kubectl operations.
Loop capped at 40 requests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from common.provider import build_model
from pydantic_ai import Agent
from pydantic_ai.usage import Usage, UsageLimits

from .models import DiagnosisDeps, DiagnosisReport

if TYPE_CHECKING:
    from orchestrator.models import FaultEvent


_SYSTEM_PROMPT = """You are a Kubernetes SRE diagnosis agent operating on a K3s cluster.
Your only actions are tool calls using the tools listed below. Do not invent tool names.

Available tools:
  kubectl-mcp: get_pods, describe_pod, get_logs, rollout_status,
               rollout_undo, apply_patch
  nixos-mcp:   get_journal, get_systemd_status, get_generations,
               rebuild_test, switch_generation, etcd_snapshot_save

Rules:
- Never name a symptom as the root cause. CrashLoopBackOff, OOMKilled, and
  ImagePullBackOff are symptoms, not root causes. Trace each symptom to the
  underlying component (wrong image tag, memory limit too low, missing secret, etc.).
- root_cause_component must be an exact Deployment/Pod/image identifier from kubectl
  output (e.g., "vigil-app:bad-tag-v9"), not a generic description.
- evidence must be a verbatim log line or event quoted from tool output.
- requires_os_level=True only when kubectl evidence is insufficient and the fault
  involves a node condition or NixOS service. Do not escalate for pure K8s faults.
- confidence below 0.6 means you need more evidence before recommending an action.
- Use kubectl-mcp tools directly for all Kubernetes operations.

apply_patch rules (avoid invalid patches):
- ALWAYS include "name" in every containers[] entry you patch.
- ALWAYS include "image" in every containers[] entry when using strategic merge patch.
- To remove a specific env var, use JSON patch type with op=remove:
    patch_type=json
    patch=[{"op":"remove","path":"/spec/template/spec/containers/0/env/INDEX"}]
  Find the correct INDEX first by calling describe_pod or get_pods to
  inspect current env.
- To set/replace a resource limit or request, use JSON patch type:
    patch_type=json
    patch=[{"op":"replace",
            "path":"/spec/template/spec/containers/0/resources/limits/memory",
            "value":"128Mi"}]
- Never send a strategic merge patch for containers[] without both "name"
  and "image" fields."""


diagnosis_agent: Agent[DiagnosisDeps, DiagnosisReport] = Agent(
    build_model(),
    deps_type=DiagnosisDeps,
    output_type=DiagnosisReport,
    retries=2,
    system_prompt=_SYSTEM_PROMPT,
)


async def run_diagnosis(
    deps: DiagnosisDeps, fault: FaultEvent
) -> tuple[DiagnosisReport, Usage]:
    """Run the Diagnosis ReAct loop and return (report, usage).

    The usage tuple captures token counts and request counts so the Orchestrator
    can aggregate across sub-agents into the RunRecord.

    Raises:
        UsageLimitExceeded: When the ReAct loop exceeds 20 LLM requests.
        UnexpectedModelBehavior: When Pydantic validation fails after all retries.
    """
    result = await diagnosis_agent.run(
        f"Diagnose fault: {fault.model_dump_json()}",
        deps=deps,
        toolsets=[deps.kubectl_mcp, deps.nixos_mcp],
        usage_limits=UsageLimits(request_limit=40),
    )
    return result.output, result.usage()
