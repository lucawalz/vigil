"""Remediation agent: executes K8s repairs via GitOps and OS repairs via NixOS rebuilds.

K8s path: branch the repo, write the corrected manifest, commit, push, open a PR,
wait for the CI gate, then trigger Flux reconciliation. OS path: nixos-rebuild test
and fall back to switch_generation.

Tool scope: git, flux, and nixos MCP clients only.
"""

from __future__ import annotations

from common import trace
from common.provider import build_model
from diagnosis.models import DiagnosisReport
from pydantic_ai import Agent
from pydantic_ai.exceptions import UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.usage import Usage, UsageLimits

from .models import RemediationDeps, RemediationResult

_SYSTEM_PROMPT = """\
You are the Remediation stage of the vigil fault-response pipeline. Execute one of
four action classes, determined by recommended_action from the DiagnosisReport.
Operate through MCP tool calls only. Do not call ssh-mcp; it is not in the toolset.

MANDATORY BRANCHING ON recommended_action:

If recommended_action == "flux_reconcile":
  1. Call flux-mcp.reconcile_kustomization(
     namespace='flux-system', name='cluster-apps').
     Do not create a branch, do not call git-mcp, do not open a PR.
  2. Return RemediationResult(success=True, ...) if the call completes without error.

If recommended_action == "git_commit_k8s":
  Inputs already present in the report:
    - DiagnosisReport.manifest_path -- repo-relative path to overwrite
    - DiagnosisReport.proposed_patch.patch_body -- full replacement manifest YAML
    - affected_resources -- list of affected Kubernetes resources

  Execute the following sequence EXACTLY ONCE (GIT_COMMIT_BUDGET=1):
    0. clone_repo(run_id=<run_id>, base_branch=<source_branch>)
       -- initialises the git-mcp session; idempotent if diagnosis already ran.
    1. create_branch(run_id=<run_id>)
       -- git-mcp returns 'branch created: remediation/run-<run_id>'.
       -- record the branch name into RemediationResult.agent_branch.
    1b. read_file(branch=<source_branch>, path=DiagnosisReport.manifest_path) to fetch
        the current declared content. If the returned content is identical to
        DiagnosisReport.proposed_patch.patch_body, the fix is already in git; escalate
        rather than opening a no-op PR.
    2. write_manifest(manifest_path=DiagnosisReport.manifest_path,
                     patch_body=DiagnosisReport.proposed_patch.patch_body)
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
         b. call delete_branch(branch=<branch from step 1>)
         c. record RemediationResult.gate_status='closed' and merge_commit_sha=None
         d. return success=False with the action trace and STOP.
    7. flux-mcp.reconcile_kustomization(namespace='flux-system', name='cluster-apps')
       -- triggers Flux to pull the merged commit immediately.

  BUDGET / NO-RETRY (GIT_COMMIT_BUDGET=1):
    Once push_branch and create_pr have been called, do NOT call create_branch,
    write_manifest, or commit_files again in this run. If the gate fails or
    reconcile_kustomization errors, return RemediationResult with the trace
    so far and STOP. The orchestrator decides the terminal outcome.

If recommended_action == "nixos_rebuild":
  1. Skip git and flux tooling entirely -- this is an OS-only repair.
  2. Use DiagnosisReport.target_host as the 'host' argument for nixos-mcp calls.
  3. Call nixos-mcp.switch_generation(host=target_host).
  4. Return RemediationResult(success=True, ...) if switch_generation completes
     without error.

If recommended_action == "git_commit_nix":
  Inputs already present in the report:
    - DiagnosisReport.manifest_path -- repo-relative path to overwrite
    - DiagnosisReport.proposed_patch.patch_body -- full replacement manifest YAML
    - DiagnosisReport.target_host -- NixOS hostname for nixos-mcp calls

  Execute the following sequence EXACTLY ONCE (GIT_COMMIT_BUDGET=1):
    0. clone_repo(run_id=<run_id>, base_branch=<source_branch>)
       -- idempotent if diagnosis already ran.
    1. create_branch(run_id=<run_id>)
    1b. read_file(branch=<source_branch>, path=DiagnosisReport.manifest_path) to fetch
        the current declared content. If identical to proposed_patch.patch_body,
        escalate.
    2. write_manifest(manifest_path=DiagnosisReport.manifest_path,
                     patch_body=DiagnosisReport.proposed_patch.patch_body)
    3. commit_files(message='fix(remediation): <short root cause summary>')
    4. push_branch()
    5. create_pr(title='<short summary>', body='<root cause + evidence>')
       -- base branch is taken from clone_repo.
    6. wait_for_gate(pr_number=<pr_number from create_pr response>)
       -- on gate failure: call close_pr, delete_branch, return success=False and STOP.
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
  - destructive_repair: True if any mutation tool was invoked (any git-mcp write
    tool, switch_generation, or trigger_reconcile).
  - merge_commit_sha: parsed from 'gate passed: merged sha=<sha>' on git_commit_k8s
    or git_commit_nix success; None otherwise.
  - agent_branch: 'remediation/run-<run_id>' on git paths; None otherwise.
  - agent_commits: list of commit SHAs from commit_files responses on git paths;
    None otherwise.
  - gate_status: 'merged' on gate success, 'closed' on gate failure, None on
    non-git paths.

If recommended_action is anything other than the four above (including "escalate"),
return RemediationResult(success=False, actions_taken=[], tool_calls_count=0,
destructive_repair=False, merge_commit_sha=None, agent_branch=None,
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
) -> tuple[RemediationResult, Usage, list[ModelMessage]]:
    if source_branch == "main":
        refused = RemediationResult(
            success=False,
            actions_taken=["refused_main_branch"],
            tool_calls_count=0,
            destructive_repair=False,
        )
        return refused, Usage(), []

    task = (
        f"Remediate the fault described in this DiagnosisReport: "
        f"{report.model_dump_json()}. "
        f"affected_resources = {report.affected_resources}. "
        f"recommended_action = {report.recommended_action}. "
        f"source_branch = {source_branch}."
    )
    async with remediation_agent.iter(
        task,
        deps=deps,
        toolsets=[deps.git_mcp, deps.flux_mcp, deps.nixos_mcp],
        usage_limits=UsageLimits(request_limit=20),
        model=model,
    ) as agent_run:
        try:
            async for _ in agent_run:
                pass
        except (UnexpectedModelBehavior, UsageLimitExceeded):
            if run_id:
                partial_msgs = agent_run.all_messages()
                if partial_msgs:
                    trace.write_trace(run_id, "remediation", partial_msgs, partial=True)
            raise
    return agent_run.result.output, agent_run.usage, agent_run.all_messages()
