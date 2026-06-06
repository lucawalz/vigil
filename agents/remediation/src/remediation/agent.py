"""Remediation agent: executes K8s repairs via GitOps and OS repairs via NixOS rebuilds.

K8s path: branch the repo, write the corrected manifest, commit, push, open a PR,
wait for the CI gate, then trigger Flux reconciliation. OS path: stage the target
generation so the running system activates it without changing the bootloader default;
the orchestrator commits the generation durably only after health is confirmed.

Tool scope: git, flux, and nixos MCP clients only.
"""

from __future__ import annotations

import os

from common import trace
from common.constants import GIT_COMMIT_BUDGET, PROTECTED_BRANCHES
from common.provider import build_model
from common.toolset_guards import (
    Breaker,
    CallBudgetToolset,
    CircuitBreakerToolset,
    CircuitBreakerTripped,
)
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
    RemediationOutputRetryExhausted,
    RemediationResult,
)

REMEDIATION_REQUEST_LIMIT: int = int(os.environ.get("REMEDIATION_REQUEST_LIMIT", "20"))

_COMMIT_TOOL_NAME = "commit_files"
_COMMIT_GENERATION_TOOL_NAME = "commit_generation"

_ESSENTIAL_MUTATING_TOOLS: dict[str, frozenset[str]] = {
    "flux_reconcile": frozenset({"reconcile_kustomization"}),
    "git_commit_k8s": frozenset(
        {"write_manifest", "commit_files", "push_branch", "create_pr"}
    ),
    "git_commit_nix": frozenset(
        {"write_manifest", "commit_files", "push_branch", "create_pr"}
    ),
    "nixos_rebuild": frozenset({"stage_generation"}),
}

_SYSTEM_PROMPT = """\
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
  Do NOT call create_branch. The branch name is provided in the task as
  agent_branch; record that value into RemediationResult.agent_branch.

  Execute the following sequence EXACTLY ONCE (GIT_COMMIT_BUDGET=1):
    0. clone_repo(run_id=<run_id>, base_branch=<source_branch>)
       -- initialises the git-mcp session; idempotent if diagnosis already ran.
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
       -- base branch is taken from clone_repo. auto-merge is enabled by git-mcp.
    6. wait_for_gate(pr_number=<pr_number from create_pr response>)
       -- on success, the response is 'gate passed: merged sha=<sha>'.
       -- extract <sha> after 'sha=' and record into RemediationResult.merge_commit_sha.
       -- record RemediationResult.gate_status='merged'.
       -- on failure (tool returns an error containing 'PR closed without merge'):
         a. call close_pr(pr_number=<pr_number>)
         b. call delete_branch(branch=<the provided agent_branch>)
         c. record RemediationResult.gate_status='closed' and merge_commit_sha=None
         d. return success=False with the action trace and STOP.
    7. flux-mcp.reconcile_kustomization(namespace='flux-system', name='cluster-apps')
       -- triggers Flux to pull the merged commit immediately.

  BUDGET / NO-RETRY (GIT_COMMIT_BUDGET=1):
    Once push_branch and create_pr have been called, do NOT call
    write_manifest or commit_files again in this run. If the gate fails or
    reconcile_kustomization errors, return RemediationResult with the trace
    so far and STOP. The orchestrator decides the terminal outcome.

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
  Do NOT call create_branch. The branch name is provided in the task as
  agent_branch; record that value into RemediationResult.agent_branch.

  Execute the following sequence EXACTLY ONCE (GIT_COMMIT_BUDGET=1):
    0. clone_repo(run_id=<run_id>, base_branch=<source_branch>)
       -- idempotent if diagnosis already ran.
    1. read_file(branch=<source_branch>, path=DiagnosisReport.manifest_path) to fetch
       the current declared content. If identical to DiagnosisReport.patch_body,
       escalate.
    2. write_manifest(manifest_path=DiagnosisReport.manifest_path,
                     patch_body=DiagnosisReport.patch_body)
    3. commit_files(message='fix(remediation): <short root cause summary>')
    4. push_branch()
    5. create_pr(title='<short summary>', body='<root cause + evidence>')
       -- base branch is taken from clone_repo.
    6. wait_for_gate(pr_number=<pr_number from create_pr response>)
       -- on gate failure: call close_pr,
          delete_branch(branch=<the provided agent_branch>),
          return success=False and STOP.
       -- on gate passed: extract merge sha, record merge_commit_sha and gate_status.
    7. After wait_for_gate returns 'gate passed', call
       nixos-mcp.trigger_reconcile(host=target_host)
       to force the on-host NixOS rebuild without waiting for the auto-reconciler timer.
  8. Return RemediationResult(success=True, ...) if trigger_reconcile completes
     without error.

  BUDGET / NO-RETRY (GIT_COMMIT_BUDGET=1):
    Same budget constraint as git_commit_k8s -- do not retry git operations.

Return a RemediationResult with:
  - success: True only if the repair action completed without error.
  - actions_taken: ordered list of tool names called.
  - tool_calls_count: total tool calls.
  - mutation_attempted: True if any mutation tool was invoked (any git-mcp write
    tool, stage_generation, or trigger_reconcile).
  - merge_commit_sha: parsed from 'gate passed: merged sha=<sha>' on git_commit_k8s
    or git_commit_nix success; None otherwise.
  - agent_branch: the agent_branch value provided in the task, on git paths;
    None otherwise.
  - agent_commits: list of commit SHAs from commit_files responses on git paths;
    None otherwise.
  - gate_status: 'merged' on gate success, 'closed' on gate failure, None on
    non-git paths.

If recommended_action is anything other than the four above (including "escalate"),
return RemediationResult(success=False, actions_taken=[], tool_calls_count=0,
mutation_attempted=False, merge_commit_sha=None, agent_branch=None,
agent_commits=None, gate_status=None) immediately with
error="unexpected_action: <value>" in actions_taken. Do not call any tools.
The orchestrator handles "escalate" before run_remediation is ever called;
this guard exists for unexpected values only."""


remediation_agent: Agent[RemediationDeps, RemediationResult] = Agent(
    build_model(),
    deps_type=RemediationDeps,
    output_type=RemediationResult,
    retries=1,
    system_prompt=_SYSTEM_PROMPT,
)


async def run_remediation(
    deps: RemediationDeps,
    report: DiagnosisReport,
    source_branch: str = "main",
    model: OpenAIChatModel | None = None,
    run_id: str = "",
    agent_branch: str = "",
    blocked_tools: frozenset[str] = frozenset(),
    breaker: Breaker | None = None,
    require_human_review: bool = False,
) -> tuple[RemediationResult, RunUsage, list[ModelMessage]]:
    if source_branch in PROTECTED_BRANCHES:
        refused = RemediationResult(
            success=False,
            actions_taken=["refused_protected_branch"],
            tool_calls_count=0,
            mutation_attempted=False,
        )
        return refused, RunUsage(), []

    essential_blocked = (
        _ESSENTIAL_MUTATING_TOOLS.get(report.recommended_action, frozenset())
        & blocked_tools
    )
    if essential_blocked:
        refused = RemediationResult(
            success=False,
            actions_taken=["refused_blocked_tool"],
            tool_calls_count=0,
            mutation_attempted=False,
        )
        return refused, RunUsage(), []

    def _allow(tool_name: str) -> bool:
        return tool_name not in blocked_tools

    def _allow_nixos(tool_name: str) -> bool:
        return tool_name != _COMMIT_GENERATION_TOOL_NAME and _allow(tool_name)

    filtered_git = (
        FilteredToolset(deps.git_mcp, filter_func=lambda _ctx, td: _allow(td.name))
        if blocked_tools
        else deps.git_mcp
    )
    git_toolset = CallBudgetToolset(
        wrapped=filtered_git,
        tool_name=_COMMIT_TOOL_NAME,
        budget=GIT_COMMIT_BUDGET,
        on_exceeded=GitCommitBudgetExceeded,
    )
    flux_toolset = (
        FilteredToolset(deps.flux_mcp, filter_func=lambda _ctx, td: _allow(td.name))
        if blocked_tools
        else deps.flux_mcp
    )
    nixos_toolset = FilteredToolset(
        deps.nixos_mcp, filter_func=lambda _ctx, td: _allow_nixos(td.name)
    )

    toolsets: list[object] = [git_toolset, flux_toolset, nixos_toolset]
    if breaker is not None:
        toolsets = [
            CircuitBreakerToolset(wrapped=ts, breaker=breaker) for ts in toolsets
        ]

    constraint_block = ""
    if blocked_tools:
        constraint_block = (
            f" These tools are blocked for this run and must not be called: "
            f"{', '.join(sorted(blocked_tools))}."
            f" If remediation requires a blocked tool,"
            f" return success=False immediately."
        )

    review_block = ""
    if require_human_review:
        review_block = (
            " HUMAN-REVIEW MODE OVERRIDE (applies only to git_commit_k8s and"
            " git_commit_nix): open the PR for a human to merge, do not gate or"
            " reconcile. After push_branch, call create_pr(..., auto_merge=false)."
            " Then STOP: do NOT call wait_for_gate and do NOT call"
            " reconcile_kustomization or trigger_reconcile. Record the provided"
            " agent_branch and agent_commits, set gate_status='awaiting_review', set"
            " merge_commit_sha=None, and return success=True because the PR was"
            " opened successfully for human review."
        )

    task = (
        f"Remediate the fault described in this DiagnosisReport: "
        f"{report.model_dump_json()}. "
        f"affected_resources = {report.affected_resources}. "
        f"recommended_action = {report.recommended_action}. "
        f"source_branch = {source_branch}."
        f" agent_branch = {agent_branch}."
        f"{constraint_block}"
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
    except GitCommitBudgetExceeded:
        if run_id:
            partial_msgs = agent_run.all_messages()
            if partial_msgs:
                trace.write_trace(run_id, "remediation", partial_msgs, partial=True)
        budget_refused = RemediationResult(
            success=False,
            actions_taken=["commit_budget_exceeded"],
            tool_calls_count=0,
            mutation_attempted=False,
        )
        return budget_refused, agent_run.usage, agent_run.all_messages()
    except UnexpectedModelBehavior as exc:
        partial_msgs = agent_run.all_messages()
        if run_id and partial_msgs:
            trace.write_trace(run_id, "remediation", partial_msgs, partial=True)
        raise RemediationOutputRetryExhausted(
            agent_run.usage, partial_msgs, exc
        ) from exc
    except UsageLimitExceeded:
        if run_id:
            partial_msgs = agent_run.all_messages()
            if partial_msgs:
                trace.write_trace(run_id, "remediation", partial_msgs, partial=True)
        raise
    except CircuitBreakerTripped:
        if run_id:
            partial_msgs = agent_run.all_messages()
            if partial_msgs:
                trace.write_trace(run_id, "remediation", partial_msgs, partial=True)
        raise
    return agent_run.result.output, agent_run.usage, agent_run.all_messages()
