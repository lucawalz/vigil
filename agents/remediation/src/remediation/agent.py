"""Remediation agent: executes K8s repairs via GitOps and OS repairs via NixOS rebuilds.

K8s and NixOS git paths: write the corrected manifest, commit, push and open a PR;
the orchestrator waits for the CI gate, merges and reconciles. OS path: stage the target
generation so the running system activates it without changing the bootloader default;
the orchestrator commits the generation durably only after health is confirmed.

Tool scope: git, flux, and nixos MCP clients only.
"""

from __future__ import annotations

import os

from common import trace
from common.constants import (
    DIAGNOSIS_FLUX_READ_TOOLS,
    DIAGNOSIS_GIT_READ_TOOLS,
    DIAGNOSIS_NIXOS_READ_TOOLS,
    GIT_COMMIT_BUDGET,
    PROTECTED_BRANCHES,
)
from common.provider import build_model
from common.toolset_guards import (
    Breaker,
    CallBudgetToolset,
    CircuitBreakerToolset,
    CircuitBreakerTripped,
)
from common.untrusted import UNTRUSTED_DATA_RULE, FencingToolset, fence_value, new_nonce
from diagnosis.models import DiagnosisReport
from pydantic_ai import Agent
from pydantic_ai.exceptions import UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.toolsets.filtered import FilteredToolset
from pydantic_ai.usage import RunUsage, UsageLimits

from .models import (
    GitCommitBudgetExceeded,
    RemediationDeps,
    RemediationOutput,
    RemediationOutputRetryExhausted,
    RemediationResult,
)

REMEDIATION_REQUEST_LIMIT: int = int(os.environ.get("REMEDIATION_REQUEST_LIMIT", "20"))

_COMMIT_TOOL_NAME = "commit_files"
_ORCHESTRATOR_OWNED_NIXOS_TOOLS = frozenset(
    {"commit_generation", "get_reconciled_revision"}
)
_ORCHESTRATOR_OWNED_GIT_TOOLS = frozenset(
    {
        "wait_for_gate",
        "close_pr",
        "delete_branch",
        "revert_commit",
        "clone_repo",
        "create_branch",
    }
)

_FENCED_REPORT_FIELDS: set[str] = {
    "root_cause",
    "root_cause_component",
    "affected_resources",
    "evidence",
}
_EXTERNAL_CONTENT_TOOLS = (
    DIAGNOSIS_GIT_READ_TOOLS
    | DIAGNOSIS_FLUX_READ_TOOLS
    | DIAGNOSIS_NIXOS_READ_TOOLS
    | frozenset(
        {
            "get_pr_status",
            "stage_generation",
            "rebuild_test",
            "etcd_snapshot_save",
            "trigger_reconcile",
        }
    )
)

_SYSTEM_PROMPT = (
    """\
You are the Remediation stage of the vigil fault-response pipeline. Execute one of
four action classes, determined by recommended_action from the DiagnosisReport.
Operate through MCP tool calls only.

MANDATORY BRANCHING ON recommended_action:

If recommended_action == "flux_reconcile":
  1. Call flux-mcp.reconcile_kustomization(
     namespace='flux-system', name='cluster-apps').
     Do not create a branch, do not call git-mcp, do not open a PR.
  2. Return RemediationResult(success=True, ...) if the call completes without error.

If recommended_action == "git_commit_k8s":
  Inputs already present in the report:
    - DiagnosisReport.manifest_path -- repo-relative path to overwrite
    - DiagnosisReport.patch_body -- full replacement manifest YAML
    - affected_resources -- list of affected Kubernetes resources

  The remediation branch has already been created and checked out for this run.
  The branch name is provided in the task as agent_branch; record that value
  into RemediationResult.agent_branch.

  Execute the following sequence EXACTLY ONCE (GIT_COMMIT_BUDGET=1):
    1. read_file(branch=<source_branch>, path=DiagnosisReport.manifest_path) to fetch
       the current declared content. If the returned content is identical to
       DiagnosisReport.patch_body, the fix is already in git; escalate
       rather than opening a no-op PR.
    2. write_manifest(manifest_path=DiagnosisReport.manifest_path,
                     patch_body=DiagnosisReport.patch_body)
    3. commit_files(message='fix(remediation): <short root cause summary>')
       -- record the SHA from 'commit: <sha>' into RemediationResult.agent_commits.
    4. push_branch()
    5. create_pr(title='<short summary>', body='<root cause + evidence>')
       -- opens the PR into the session's base branch.
          Then STOP: the orchestrator waits for the CI gate, merges, and reconciles.

  BUDGET / NO-RETRY (GIT_COMMIT_BUDGET=1):
    Once push_branch and create_pr have been called, do NOT call write_manifest
    or commit_files again. If any step errors, return the trace so far and STOP.

If recommended_action == "nixos_rebuild":
  1. Skip git and flux tooling entirely -- this is an OS-only repair.
  2. Use DiagnosisReport.target_host as the 'host' argument for nixos-mcp calls.
  3. Call nixos-mcp.get_generations(host=target_host) to determine the target
     generation number N to activate.
  4. Call nixos-mcp.stage_generation(host=target_host, generation=N). This is a
     non-durable activation: the running system switches to generation N and the
     dead-man's-switch rollback timer is armed, but the bootloader default is
     unchanged. Then STOP.
  5. Do NOT call commit_generation. The orchestrator commits the generation
     durably and deterministically only after the Watchdog confirms health; if
     health is never confirmed, the armed timer reboots the host back to the
     prior generation.
  6. Return RemediationResult(success=True, ...) if stage_generation completes
     without error.

If recommended_action == "git_commit_nix":
  Inputs already present in the report:
    - DiagnosisReport.manifest_path -- repo-relative path to overwrite
    - DiagnosisReport.patch_body -- full replacement manifest YAML
    - DiagnosisReport.target_host -- NixOS hostname for nixos-mcp calls

  The remediation branch has already been created and checked out for this run.
  The branch name is provided in the task as agent_branch; record that value
  into RemediationResult.agent_branch.

  Execute the following sequence EXACTLY ONCE (GIT_COMMIT_BUDGET=1):
    1. read_file(branch=<source_branch>, path=DiagnosisReport.manifest_path) to fetch
       the current declared content. If identical to DiagnosisReport.patch_body,
       escalate.
    2. write_manifest(manifest_path=DiagnosisReport.manifest_path,
                     patch_body=DiagnosisReport.patch_body)
    3. commit_files(message='fix(remediation): <short root cause summary>')
    4. push_branch()
    5. create_pr(title='<short summary>', body='<root cause + evidence>')
       -- opens the PR into the session's base branch.
          Then STOP: the orchestrator waits for the CI gate, merges, and reconciles.

  BUDGET / NO-RETRY (GIT_COMMIT_BUDGET=1):
    Same budget constraint as git_commit_k8s -- do not retry git operations.

Return a RemediationResult with:
  - success: True only if the repair action completed without error.
  - actions_taken: ordered list of tool names called.
  - tool_calls_count: total tool calls.
  - mutation_attempted: True if any mutation tool was invoked (any git-mcp write
    tool, stage_generation, or trigger_reconcile).
  - agent_branch: the agent_branch value provided in the task, on git paths;
    None otherwise.
  - agent_commits: list of commit SHAs from commit_files responses on git paths;
    None otherwise.

If recommended_action is anything other than the four above (including "escalate"),
return RemediationResult(success=False, actions_taken=[], tool_calls_count=0,
mutation_attempted=False, agent_branch=None, agent_commits=None) immediately with
error="unexpected_action: <value>" in actions_taken. Do not call any tools.
The orchestrator handles "escalate" before run_remediation is ever called;
this guard exists for unexpected values only.

"""
    + UNTRUSTED_DATA_RULE
)


remediation_agent: Agent[RemediationDeps, RemediationOutput] = Agent(
    build_model(),
    deps_type=RemediationDeps,
    output_type=RemediationOutput,
    retries=1,
    system_prompt=_SYSTEM_PROMPT,
)


def _preflight_refusal(
    report: DiagnosisReport,
    source_branch: str,
) -> RemediationResult | None:
    """Return a deterministic refusal when guardrails forbid running the agent."""
    if source_branch in PROTECTED_BRANCHES:
        return RemediationResult(
            success=False,
            actions_taken=["refused_protected_branch"],
            tool_calls_count=0,
            mutation_attempted=False,
        )
    return None


def _build_review_block(require_human_review: bool) -> str:
    if not require_human_review:
        return ""
    return (
        " HUMAN-REVIEW MODE OVERRIDE (applies only to git_commit_k8s and"
        " git_commit_nix): the PR stays open for a human to merge. After"
        " create_pr(...), STOP: do NOT call reconcile_kustomization or"
        " trigger_reconcile. Record the provided agent_branch and agent_commits"
        " and return success=True once the PR is open."
    )


def _persist_partial_trace(run_id: str, partial_msgs: list[ModelMessage]) -> None:
    if run_id and partial_msgs:
        trace.write_trace(run_id, "remediation", partial_msgs, partial=True)


async def run_remediation(
    deps: RemediationDeps,
    report: DiagnosisReport,
    source_branch: str = "main",
    model: OpenAIChatModel | None = None,
    run_id: str = "",
    agent_branch: str = "",
    breaker: Breaker | None = None,
    require_human_review: bool = False,
) -> tuple[RemediationResult, RunUsage, list[ModelMessage]]:
    refusal = _preflight_refusal(report, source_branch)
    if refusal is not None:
        return refusal, RunUsage(), []

    git_toolset = FilteredToolset(
        CallBudgetToolset(
            wrapped=deps.git_mcp,
            tool_name=_COMMIT_TOOL_NAME,
            budget=GIT_COMMIT_BUDGET,
            on_exceeded=GitCommitBudgetExceeded,
        ),
        filter_func=lambda _ctx, td: td.name not in _ORCHESTRATOR_OWNED_GIT_TOOLS,
    )
    nixos_toolset = FilteredToolset(
        deps.nixos_mcp,
        filter_func=lambda _ctx, td: td.name not in _ORCHESTRATOR_OWNED_NIXOS_TOOLS,
    )

    nonce = new_nonce()
    toolsets: list[object] = [
        FencingToolset(wrapped=ts, nonce=nonce, tools=_EXTERNAL_CONTENT_TOOLS)
        for ts in [git_toolset, deps.flux_mcp, nixos_toolset]
    ]
    if breaker is not None:
        toolsets = [
            CircuitBreakerToolset(wrapped=ts, breaker=breaker) for ts in toolsets
        ]

    review_block = _build_review_block(require_human_review)
    fenced_fields = "".join(
        f"{field}:\n{fence_value(getattr(report, field), field, nonce)}\n"
        for field in sorted(_FENCED_REPORT_FIELDS)
    )
    task = (
        f"Remediate the fault described in this DiagnosisReport: "
        f"{report.model_dump_json(exclude=_FENCED_REPORT_FIELDS)}. "
        f"{fenced_fields}"
        f"recommended_action = {report.recommended_action}. "
        f"source_branch = {source_branch}."
        f" agent_branch = {agent_branch}."
        f"{review_block}"
    )
    try:
        async with remediation_agent.iter(
            task,
            deps=deps,
            toolsets=toolsets,
            usage_limits=UsageLimits(request_limit=REMEDIATION_REQUEST_LIMIT),
            model=model,
        ) as agent_run:
            async for _ in agent_run:
                pass
        if agent_run.result is None:
            raise UnexpectedModelBehavior("remediation run ended without a result")
    except GitCommitBudgetExceeded:
        _persist_partial_trace(run_id, agent_run.all_messages())
        budget_refused = RemediationResult(
            success=False,
            actions_taken=["commit_budget_exceeded"],
            tool_calls_count=0,
            mutation_attempted=False,
            budget_refused=True,
        )
        return budget_refused, agent_run.usage, agent_run.all_messages()
    except UnexpectedModelBehavior as exc:
        partial_msgs = agent_run.all_messages()
        _persist_partial_trace(run_id, partial_msgs)
        raise RemediationOutputRetryExhausted(
            agent_run.usage, partial_msgs, exc
        ) from exc
    except UsageLimitExceeded:
        _persist_partial_trace(run_id, agent_run.all_messages())
        raise
    except CircuitBreakerTripped:
        _persist_partial_trace(run_id, agent_run.all_messages())
        raise
    return (
        RemediationResult(**agent_run.result.output.model_dump()),
        agent_run.usage,
        agent_run.all_messages(),
    )
