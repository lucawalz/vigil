"""Remediation agent structural + contract tests.

Asserts git-mcp-first ordering at the prompt level and that the
toolset scope excludes ssh_mcp and kubectl_mcp.
"""

from __future__ import annotations

import inspect
import os

os.environ.setdefault("LLM_MODEL_NAME", "test-model")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:1/v1")
os.environ.setdefault("OLLAMA_API_KEY", "sk-test")

import remediation.agent as _rem_agent_mod
from diagnosis.models import DiagnosisReport
from pydantic_ai import Agent
from remediation.agent import remediation_agent, run_remediation
from remediation.models import RemediationDeps, RemediationResult


def test_remediation_agent_is_agent_instance() -> None:
    assert isinstance(remediation_agent, Agent)


def test_run_remediation_is_coroutine() -> None:
    assert inspect.iscoroutinefunction(run_remediation)


def test_run_remediation_toolsets_exclude_ssh() -> None:
    """Remediation scope is git+flux+nixos only; no ssh or kubectl."""
    source = inspect.getsource(run_remediation)
    assert "toolsets=[deps.git_mcp, deps.flux_mcp, deps.nixos_mcp]" in source
    assert "ssh_mcp" not in source
    assert "kubectl_mcp" not in source


def test_run_remediation_enforces_usage_limit() -> None:
    """20-request ceiling applies to Remediation loop too."""
    source = inspect.getsource(run_remediation)
    assert "UsageLimits(request_limit=20)" in source


def test_remediation_prompt_mandates_git_commit_sequence() -> None:
    """All seven git-mcp tool names must appear in the module source."""
    mod_source = inspect.getsource(_rem_agent_mod)
    assert "create_branch" in mod_source
    assert "write_manifest" in mod_source
    assert "commit_files" in mod_source
    assert "push_branch" in mod_source
    assert "create_pr" in mod_source
    assert "wait_for_gate" in mod_source
    assert "reconcile_kustomization" in mod_source
    has_emphasis = any(
        kw in mod_source for kw in ("FIRST", "MANDATORY", "MUST", "exactly once")
    )
    assert has_emphasis, "Prompt must emphasise ordering of git-mcp sequence"


def test_remediation_prompt_no_suspend_or_apply() -> None:
    """Retired tools must not appear anywhere in the remediation agent module."""
    mod_source = inspect.getsource(_rem_agent_mod)
    assert "suspend_kustomization" not in mod_source
    assert "resume_kustomization" not in mod_source
    assert "apply_patch" not in mod_source
    assert "rollout_undo" not in mod_source


def test_remediation_prompt_gate_failure_cleanup() -> None:
    """Gate-failure cleanup path must reference close_pr and delete_branch."""
    mod_source = inspect.getsource(_rem_agent_mod)
    assert "close_pr" in mod_source
    assert "delete_branch" in mod_source


def test_remediation_prompt_references_affected_resources() -> None:
    """affected_resources still flows to reconcile_kustomization and revert scope."""
    mod_source = inspect.getsource(_rem_agent_mod)
    assert "affected_resources" in mod_source


def test_run_remediation_signature() -> None:
    sig = inspect.signature(run_remediation)
    params = list(sig.parameters.values())
    assert len(params) == 3
    assert params[0].name == "deps"
    assert params[1].name == "report"
    ann_report = params[1].annotation
    assert ann_report is DiagnosisReport or (
        isinstance(ann_report, str) and "DiagnosisReport" in ann_report
    )
    assert params[2].name == "model"
    assert params[2].default is None


def test_remediation_result_fields_stable() -> None:
    """Guard: RemediationResult schema must not drift."""
    fields = set(RemediationResult.model_fields.keys())
    assert fields == {
        "success",
        "actions_taken",
        "tool_calls_count",
        "destructive_repair",
        "merge_commit_sha",
        "agent_branch",
        "agent_commits",
        "gate_status",
    }


def test_run_remediation_returns_tuple_with_usage() -> None:
    """Orchestrator needs usage tuple for token aggregation."""
    source = inspect.getsource(run_remediation)
    assert "result.usage" in source
    assert "result.all_messages()" in source
    assert "return result.output, result.usage, result.all_messages()" in source


def test_remediation_prompt_dispatch_branches() -> None:
    mod_source = inspect.getsource(_rem_agent_mod)
    assert "flux_reconcile" in mod_source
    assert "git_commit_k8s" in mod_source
    assert "nixos_rebuild" in mod_source
    assert "git_commit_nix" in mod_source
    old_branch_discriminant = "requires_os" + "_level"
    assert old_branch_discriminant not in mod_source


def test_remediation_deps_has_git_mcp() -> None:
    """RemediationDeps must expose git_mcp and must not expose kubectl_mcp."""
    assert "git_mcp" in RemediationDeps.__dataclass_fields__
    assert "kubectl_mcp" not in RemediationDeps.__dataclass_fields__
