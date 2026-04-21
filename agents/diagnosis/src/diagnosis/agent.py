"""Diagnosis agent: ReAct loop over kubectl/ssh/nixos MCP tools.

Emits a structured DiagnosisReport per run.
Tool scope: kubectl, ssh, and nixos MCP clients only.
Loop capped at 20 requests.
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
Your only actions are tool calls to kubectl-mcp, ssh-mcp, and nixos-mcp.

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
- Use kubectl-mcp tools directly for all Kubernetes operations — never pass MCP server names as commands to run_allowed_command."""


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
        toolsets=[deps.kubectl_mcp, deps.ssh_mcp, deps.nixos_mcp],
        usage_limits=UsageLimits(request_limit=20),
    )
    return result.output, result.usage()
