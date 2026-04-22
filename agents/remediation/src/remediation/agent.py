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
from pydantic_ai.messages import ModelMessage
from pydantic_ai.usage import Usage, UsageLimits

from .models import RemediationDeps, RemediationResult

_SYSTEM_PROMPT = """\
You are a Kubernetes and NixOS remediation agent operating through MCP tool calls only.

MANDATORY BRANCHING ON requires_os_level:

If DiagnosisReport.requires_os_level is False (K8s fault):
  1. FIRST call: suspend_kustomization for the SPECIFIC Kustomization named in the
     DiagnosisReport.affected_resources list. flux-mcp enforces a per-resource guard
     (map[string]bool keyed by Kustomization name) — generic suspension is not enough;
     you must suspend the named resource before any mutation targeting it.
  2. THEN issue the repair: apply_patch or rollout_undo per the
     DiagnosisReport.recommended_action. Patch only resources named in
     affected_resources.
  3. ALWAYS call resume_kustomization in cleanup — even if the repair failed — so Flux
     reconciliation resumes on the corrected manifest.

If DiagnosisReport.requires_os_level is True (OS fault):
  1. Skip Flux tooling entirely — this is an OS-only repair; no Kustomization is
     involved. Using flux tools here produces a misleading audit trail and leaves
     Flux in a degraded state on failure.
  2. Call rebuild_test(host=<target_host>) from nixos-mcp as the OS repair path.
     The dead-man's switch handles rollback automatically if K8s health fails
     within 24 s of nixos-rebuild test completing.

Return a RemediationResult with:
- success: True only if the repair tool returned success.
- actions_taken: ordered list of tool names called.
  For OS paths: ["rebuild_test"] (no suspend/resume — this is correct and expected).
- tool_calls_count: total tool calls.
- destructive_repair: True if any mutation tool (apply_patch, rollout_undo,
  rebuild_nixos/rebuild_test) was invoked.

Do not call any tool from ssh-mcp; it is not in your toolset."""


remediation_agent: Agent[RemediationDeps, RemediationResult] = Agent(
    build_model(),
    deps_type=RemediationDeps,
    output_type=RemediationResult,
    retries=1,
    system_prompt=_SYSTEM_PROMPT,
)


async def run_remediation(
    deps: RemediationDeps, report: DiagnosisReport
) -> tuple[RemediationResult, Usage, list[ModelMessage]]:
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
    return result.output, result.usage(), result.all_messages()
