"""Remediation agent: executes K8s repairs via GitOps and OS repairs via NixOS rebuilds.

K8s path: branch the repo, write the corrected manifest, commit, push, open a PR,
wait for the CI gate, then trigger Flux reconciliation. OS path: nixos-rebuild test
and fall back to switch_generation.

Tool scope: git, flux, and nixos MCP clients only.
"""

from __future__ import annotations

from common.provider import build_model
from diagnosis.models import DiagnosisReport
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.usage import Usage, UsageLimits

from .models import RemediationDeps, RemediationResult

_SYSTEM_PROMPT = """\
You are a Kubernetes and NixOS remediation agent operating through MCP tool calls only.

MANDATORY BRANCHING ON requires_os_level:

If DiagnosisReport.requires_os_level is False (K8s fault):
  Inputs already present in the report:
    - DiagnosisReport.manifest_path -- repo-relative path to overwrite
    - DiagnosisReport.proposed_patch.patch_body -- full replacement manifest YAML

  Execute the following sequence EXACTLY ONCE (GIT_COMMIT_BUDGET=1):
    1. create_branch(run_id=<run_id>)
       -- git-mcp returns 'branch created: remediation/run-<run_id>'.
       -- record the branch name into RemediationResult.agent_branch.
    2. write_manifest(manifest_path=DiagnosisReport.manifest_path,
                     patch_body=DiagnosisReport.proposed_patch.patch_body)
    3. commit_files(message='fix(remediation): <short root cause summary>')
       -- record the SHA from 'commit: <sha>' into RemediationResult.agent_commits.
    4. push_branch()
    5. create_pr(title='<short summary>', body='<root cause + evidence>', base='main')
       -- auto-merge is already enabled by git-mcp.
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

If DiagnosisReport.requires_os_level is True (OS fault):
  1. Skip git, flux, and kubectl tooling entirely -- this is an OS-only repair.
  2. Use DiagnosisReport.target_host as the 'host' argument for all nixos-mcp calls.
  3. Call rebuild_test(host=<target_host>) first. Parse the output:
     - 'nixos-rebuild exit: 0' AND 'k8s-node-ready: True' ->
       success; return success=True.
     - Any other result -> proceed to generation rollback (step 4).
  4. Generation rollback:
     a. Call get_generations(host=<target_host>) to list available generations.
     b. If there is a previous (older) generation:
        call switch_generation(host, prev_gen).
        If only one generation exists: call switch_generation(host, that_gen)
        anyway -- switch-to-configuration switch re-applies the config and
        restarts stopped services even when the generation number does not change.
     c. Return success=True if switch_generation completes without error.

Return a RemediationResult with:
  - success: True only if the repair tool returned success (gate merged AND
    reconcile_kustomization returned without error for K8s, or
    rebuild_test/switch_generation succeeded for OS).
  - actions_taken: ordered list of tool names called.
  - tool_calls_count: total tool calls.
  - destructive_repair: True if any mutation tool was invoked (any git-mcp
    write tool, or rebuild_nixos/rebuild_test).
  - merge_commit_sha: parsed from 'gate passed: merged sha=<sha>' on K8s success;
    None on gate failure or OS path.
  - agent_branch: 'remediation/run-<run_id>' on K8s path; None on OS path.
  - agent_commits: list of commit SHAs from commit_files responses; None on OS path.
  - gate_status: 'merged' on K8s gate success, 'closed' on gate failure,
    None on OS path.

Do not call any tool from ssh-mcp; it is not in the toolset.

If recommended_action is anything other than 'git_commit' or 'rebuild_nixos',
return immediately with success=False, actions_taken=[], tool_calls_count=0,
destructive_repair=False, and all new optional fields=None. Do not call any tools."""


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
    model: OpenAIChatModel | None = None,
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
        toolsets=[deps.git_mcp, deps.flux_mcp, deps.nixos_mcp],
        usage_limits=UsageLimits(request_limit=20),
        model=model,
    )
    return result.output, result.usage(), result.all_messages()
