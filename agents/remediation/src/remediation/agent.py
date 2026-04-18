"""Remediation agent: executes K8s + OS fixes via MCP tools.

suspend_kustomization is the mandatory first tool call before any K8s mutation.
This is enforced at two layers:
  1. System prompt (this module) instructs the LLM explicitly.
  2. flux-mcp rejects mutations without prior suspension via a per-resource guard.

Tool scope: kubectl, flux, and nixos MCP clients only.
"""

from __future__ import annotations

from common.provider import build_model
from diagnosis.models import DiagnosisReport
from pydantic_ai import Agent
from pydantic_ai.usage import Usage, UsageLimits

from .models import RemediationDeps, RemediationResult

_SYSTEM_PROMPT = """You are a Kubernetes remediation agent operating through MCP tool calls only.

MANDATORY TOOL CALL ORDER:
1. FIRST call: suspend_kustomization for the SPECIFIC Kustomization named in the
   DiagnosisReport.affected_resources list. flux-mcp enforces a per-resource guard
   (map[string]bool keyed by Kustomization name) — generic suspension is not enough;
   you must suspend the named resource before any mutation targeting it.
2. THEN issue the repair: apply_patch, rollout_undo, or rebuild_nixos per the
   DiagnosisReport.recommended_action. Patch only resources named in affected_resources.
3. ALWAYS call resume_kustomization in cleanup — even if the repair failed — so Flux
   reconciliation resumes on the corrected manifest (or re-applies the broken Git state
   if the repair was wrong, which is the Watchdog's signal to trigger rollback).

Return a RemediationResult with:
- success: True only if the repair tool returned success AND resume_kustomization was called.
- actions_taken: ordered list of tool names called (e.g., ["suspend_kustomization",
  "apply_patch", "resume_kustomization"]).
- tool_calls_count: total count of tool calls including suspend/resume.
- destructive_repair: True if any mutation tool (apply_patch, rollout_undo, rebuild_nixos)
  was invoked -- used for audit/safety tracking by the Orchestrator.

Do not call any tool from ssh-mcp; it is not in your toolset.
Do not call any kubectl mutation before suspend_kustomization for the target resource."""


remediation_agent: Agent[RemediationDeps, RemediationResult] = Agent(
    build_model(),
    deps_type=RemediationDeps,
    output_type=RemediationResult,
    retries=1,
    system_prompt=_SYSTEM_PROMPT,
)


async def run_remediation(
    deps: RemediationDeps, report: DiagnosisReport
) -> tuple[RemediationResult, Usage]:
    """Run the Remediation agent and return (result, usage).

    The usage tuple captures token counts and request counts so the Orchestrator
    can aggregate across sub-agents into the RunRecord.

    Raises:
        UsageLimitExceeded: When the agent exceeds 20 LLM requests.
        UnexpectedModelBehavior: When Pydantic validation fails after all retries.
    """
    task = (
        f"Remediate the fault described in this DiagnosisReport: "
        f"{report.model_dump_json()}. "
        f"affected_resources = {report.affected_resources}. "
        f"recommended_action = {report.recommended_action}."
    )
    result = await remediation_agent.run(
        task,
        deps=deps,
        toolsets=[deps.kubectl_mcp, deps.flux_mcp, deps.nixos_mcp],
        usage_limits=UsageLimits(request_limit=20),
    )
    return result.output, result.usage()
