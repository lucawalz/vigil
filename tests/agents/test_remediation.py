"""Remediation agent structural + contract tests.

Asserts git-mcp-first ordering at the prompt level and that the
toolset scope excludes ssh_mcp and kubectl_mcp.
"""

from __future__ import annotations

import inspect
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("LLM_MODEL_NAME", "test-model")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:1/v1")
os.environ.setdefault("OLLAMA_API_KEY", "sk-test")

import remediation.agent as _rem_agent_mod
from common.constants import GIT_COMMIT_BUDGET, PROTECTED_BRANCHES
from common.toolset_guards import CallBudgetToolset
from diagnosis.models import DiagnosisReport
from pydantic_ai import Agent
from remediation.agent import remediation_agent, run_remediation
from remediation.models import (
    GitCommitBudgetExceeded,
    RemediationDeps,
    RemediationResult,
)


def _escalate_report() -> DiagnosisReport:
    return DiagnosisReport(
        root_cause="root cause sentence",
        root_cause_component="Deployment/vigil-app",
        severity="high",
        evidence="verbatim log line",
        drift_classification="no_drift",
        recommended_action="escalate",
        confidence=0.9,
        affected_resources=["Deployment/vigil-app"],
    )


def _deps(git_mcp: AsyncMock) -> RemediationDeps:
    return RemediationDeps(
        git_mcp=git_mcp,
        flux_mcp=AsyncMock(),
        nixos_mcp=AsyncMock(),
    )


def test_remediation_agent_is_agent_instance() -> None:
    assert isinstance(remediation_agent, Agent)


def test_run_remediation_is_coroutine() -> None:
    assert inspect.iscoroutinefunction(run_remediation)


def test_run_remediation_toolsets_exclude_ssh() -> None:
    """Remediation scope is git+flux+nixos only; no ssh or kubectl."""
    source = inspect.getsource(run_remediation)
    assert "[git_toolset, flux_toolset, nixos_toolset]" in source
    assert "ssh_mcp" not in source
    assert "kubectl_mcp" not in source


def test_run_remediation_enforces_usage_limit() -> None:
    """Request ceiling applies to Remediation loop via a named constant."""
    source = inspect.getsource(run_remediation)
    assert "UsageLimits(request_limit=REMEDIATION_REQUEST_LIMIT)" in source
    assert _rem_agent_mod.REMEDIATION_REQUEST_LIMIT == 20


def test_remediation_prompt_mandates_git_commit_sequence() -> None:
    """The git-mcp tool names of the commit sequence must appear in module source."""
    mod_source = inspect.getsource(_rem_agent_mod)
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
    params = {p.name: p for p in sig.parameters.values()}
    assert "deps" in params
    assert "report" in params
    ann_report = params["report"].annotation
    assert ann_report is DiagnosisReport or (
        isinstance(ann_report, str) and "DiagnosisReport" in ann_report
    )
    assert params["source_branch"].default == "main"
    assert params["model"].default is None
    assert "run_id" in params
    assert params["run_id"].default == ""


def test_remediation_result_fields_stable() -> None:
    """Guard: RemediationResult schema must not drift."""
    fields = set(RemediationResult.model_fields.keys())
    assert fields == {
        "success",
        "actions_taken",
        "tool_calls_count",
        "mutation_attempted",
        "merge_commit_sha",
        "agent_branch",
        "agent_commits",
        "gate_status",
    }


def test_run_remediation_returns_tuple_with_usage() -> None:
    """Orchestrator needs usage tuple for token aggregation."""
    source = inspect.getsource(run_remediation)
    assert "agent_run.usage" in source
    assert "agent_run.all_messages()" in source
    assert "agent_run.result.output" in source


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


def test_remediation_prompt_create_pr_has_no_base_arg() -> None:
    mod_source = inspect.getsource(_rem_agent_mod)
    assert "base='main'" not in mod_source
    assert "base=<source_branch>" not in mod_source
    assert "create_pr" in mod_source


def test_run_remediation_accepts_source_branch_param() -> None:
    sig = inspect.signature(run_remediation)
    assert "source_branch" in sig.parameters
    assert sig.parameters["source_branch"].default == "main"


async def test_call_budget_allows_then_raises() -> None:
    """First commit_files passes; the second exceeds GIT_COMMIT_BUDGET=1."""
    assert GIT_COMMIT_BUDGET == 1
    wrapped = AsyncMock()
    wrapped.call_tool = AsyncMock(return_value={"content": "commit: abc"})
    guard = CallBudgetToolset(
        wrapped=wrapped,
        tool_name="commit_files",
        budget=GIT_COMMIT_BUDGET,
        on_exceeded=GitCommitBudgetExceeded,
    )
    ctx = MagicMock()
    tool = MagicMock()

    await guard.call_tool("commit_files", {}, ctx, tool)
    with pytest.raises(GitCommitBudgetExceeded):
        await guard.call_tool("commit_files", {}, ctx, tool)


async def test_call_budget_ignores_other_tools() -> None:
    """Non-budgeted tools are never throttled."""
    wrapped = AsyncMock()
    wrapped.call_tool = AsyncMock(return_value={"content": "ok"})
    guard = CallBudgetToolset(
        wrapped=wrapped,
        tool_name="commit_files",
        budget=1,
        on_exceeded=GitCommitBudgetExceeded,
    )
    ctx = MagicMock()
    tool = MagicMock()

    for _ in range(5):
        await guard.call_tool("push_branch", {}, ctx, tool)
    assert wrapped.call_tool.await_count == 5


async def test_run_remediation_surfaces_budget_exceeded(
    mock_git_mcp: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A GitCommitBudgetExceeded inside the loop yields success=False, not a crash.

    pydantic-ai's iter() is an @asynccontextmanager that records the node error and
    re-raises it from its own __aexit__, even when the body already handled it. This
    fake reproduces that teardown re-raise so a handler placed inside the async with
    block (which the contextmanager re-raise discards) fails this test, while a
    handler wrapping the async with block passes it.
    """

    class _FakeRun:
        _node_error: BaseException | None = None

        async def __aenter__(self) -> "_FakeRun":
            return self

        async def __aexit__(
            self, exc_type: object, exc: BaseException | None, tb: object
        ) -> bool:
            if self._node_error is not None:
                raise self._node_error
            return False

        def __aiter__(self) -> "_FakeRun":
            return self

        async def __anext__(self) -> object:
            self._node_error = GitCommitBudgetExceeded(
                "commit_files call budget of 1 exhausted"
            )
            raise self._node_error

        def all_messages(self) -> list[object]:
            return []

        @property
        def usage(self) -> object:
            return MagicMock()

    monkeypatch.setattr(
        _rem_agent_mod.remediation_agent, "iter", lambda *a, **k: _FakeRun()
    )

    result, _usage, _msgs = await run_remediation(
        deps=_deps(mock_git_mcp),
        report=_escalate_report(),
        source_branch="remediation/run-x",
        run_id="run-x",
    )
    assert isinstance(result, RemediationResult)
    assert result.success is False
    assert "commit_budget_exceeded" in result.actions_taken


def test_protected_branches_default_includes_main_and_master() -> None:
    assert "main" in PROTECTED_BRANCHES
    assert "master" in PROTECTED_BRANCHES


async def test_run_remediation_refuses_master_branch(
    mock_git_mcp: AsyncMock,
) -> None:
    result, _usage, _msgs = await run_remediation(
        deps=_deps(mock_git_mcp),
        report=_escalate_report(),
        source_branch="master",
    )
    assert result.success is False
    assert result.actions_taken == ["refused_protected_branch"]
    mock_git_mcp.call_tool.assert_not_awaited()


async def test_run_remediation_refuses_every_protected_branch(
    mock_git_mcp: AsyncMock,
) -> None:
    for branch in PROTECTED_BRANCHES:
        result, _usage, _msgs = await run_remediation(
            deps=_deps(mock_git_mcp),
            report=_escalate_report(),
            source_branch=branch,
        )
        assert result.success is False
        assert result.actions_taken == ["refused_protected_branch"]


def _git_commit_report() -> DiagnosisReport:
    return DiagnosisReport(
        root_cause="wrong image tag",
        root_cause_component="Deployment/vigil-app",
        severity="high",
        evidence="Failed to pull image vigil-app:bad-tag",
        drift_classification="declared_drift",
        recommended_action="git_commit_k8s",
        confidence=0.55,
        affected_resources=["default/vigil-app"],
        manifest_path="apps/vigil-app.yaml",
        patch_body="apiVersion: apps/v1\n",
    )


def test_run_remediation_accepts_require_human_review_param() -> None:
    sig = inspect.signature(run_remediation)
    assert "require_human_review" in sig.parameters
    assert sig.parameters["require_human_review"].default is False


async def test_run_remediation_human_review_overrides_gate_waiting(
    mock_git_mcp: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """require_human_review=True opens a PR for a human and skips gate-waiting."""
    captured: dict[str, str] = {}
    reached = RemediationResult(
        success=True,
        actions_taken=["clone_repo", "create_pr"],
        tool_calls_count=2,
        mutation_attempted=True,
        agent_branch="remediation/run-x",
        agent_commits=["abc1234"],
        gate_status="awaiting_review",
    )

    class _FakeRun:
        async def __aenter__(self) -> "_FakeRun":
            return self

        async def __aexit__(self, *args: object) -> bool:
            return False

        def __aiter__(self) -> "_FakeRun":
            return self

        async def __anext__(self) -> object:
            raise StopAsyncIteration

        def all_messages(self) -> list[object]:
            return []

        @property
        def usage(self) -> object:
            return MagicMock()

        @property
        def result(self) -> object:
            return MagicMock(output=reached)

    def _fake_iter(task: str, *a: object, **k: object) -> _FakeRun:
        captured["task"] = task
        return _FakeRun()

    monkeypatch.setattr(_rem_agent_mod.remediation_agent, "iter", _fake_iter)

    result, _usage, _msgs = await run_remediation(
        deps=_deps(mock_git_mcp),
        report=_git_commit_report(),
        source_branch="remediation/run-x",
        require_human_review=True,
    )

    task = captured["task"]
    assert "auto_merge=false" in task
    assert "awaiting_review" in task
    assert "HUMAN-REVIEW MODE" in task
    assert result.gate_status == "awaiting_review"


async def test_run_remediation_default_omits_human_review_block(
    mock_git_mcp: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The default (auto) path must not inject the human-review override."""
    captured: dict[str, str] = {}

    class _FakeRun:
        async def __aenter__(self) -> "_FakeRun":
            return self

        async def __aexit__(self, *args: object) -> bool:
            return False

        def __aiter__(self) -> "_FakeRun":
            return self

        async def __anext__(self) -> object:
            raise StopAsyncIteration

        def all_messages(self) -> list[object]:
            return []

        @property
        def usage(self) -> object:
            return MagicMock()

        @property
        def result(self) -> object:
            return MagicMock(output=MagicMock())

    def _fake_iter(task: str, *a: object, **k: object) -> _FakeRun:
        captured["task"] = task
        return _FakeRun()

    monkeypatch.setattr(_rem_agent_mod.remediation_agent, "iter", _fake_iter)

    await run_remediation(
        deps=_deps(mock_git_mcp),
        report=_git_commit_report(),
        source_branch="remediation/run-x",
    )

    assert "HUMAN-REVIEW MODE" not in captured["task"]
    assert "auto_merge=false" not in captured["task"]


async def test_run_remediation_refuses_when_essential_tool_blocked(
    mock_git_mcp: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A blocked essential git tool yields a deterministic refusal with no model run."""

    def _fail_iter(*a: object, **k: object) -> object:
        raise AssertionError("agent loop must not run when essential tool is blocked")

    monkeypatch.setattr(_rem_agent_mod.remediation_agent, "iter", _fail_iter)

    result, _usage, msgs = await run_remediation(
        deps=_deps(mock_git_mcp),
        report=_git_commit_report(),
        source_branch="remediation/run-x",
        blocked_tools=frozenset({"write_manifest", "commit_files", "create_pr"}),
    )
    assert result.success is False
    assert result.actions_taken == ["refused_blocked_tool"]
    assert result.mutation_attempted is False
    assert msgs == []
    mock_git_mcp.call_tool.assert_not_awaited()


async def test_run_remediation_partial_block_reaches_agent(
    mock_git_mcp: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Blocking a tool outside the action's essential set must not early-return."""
    reached = RemediationResult(
        success=True,
        actions_taken=["clone_repo"],
        tool_calls_count=1,
        mutation_attempted=False,
    )

    class _FakeRun:
        async def __aenter__(self) -> "_FakeRun":
            return self

        async def __aexit__(self, *args: object) -> bool:
            return False

        def __aiter__(self) -> "_FakeRun":
            return self

        async def __anext__(self) -> object:
            raise StopAsyncIteration

        def all_messages(self) -> list[object]:
            return []

        @property
        def usage(self) -> object:
            return MagicMock()

        @property
        def result(self) -> object:
            return MagicMock(output=reached)

    monkeypatch.setattr(
        _rem_agent_mod.remediation_agent, "iter", lambda *a, **k: _FakeRun()
    )

    result, _usage, _msgs = await run_remediation(
        deps=_deps(mock_git_mcp),
        report=_git_commit_report(),
        source_branch="remediation/run-x",
        blocked_tools=frozenset({"reconcile_kustomization"}),
    )
    assert result is reached
    assert result.actions_taken != ["refused_blocked_tool"]


async def test_run_remediation_allows_non_protected_branch(
    mock_git_mcp: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A remediation/run-* branch must pass the guard and reach the agent loop."""
    reached = RemediationResult(
        success=True,
        actions_taken=["clone_repo"],
        tool_calls_count=1,
        mutation_attempted=False,
    )

    class _FakeRun:
        async def __aenter__(self) -> "_FakeRun":
            return self

        async def __aexit__(self, *args: object) -> bool:
            return False

        def __aiter__(self) -> "_FakeRun":
            return self

        async def __anext__(self) -> object:
            raise StopAsyncIteration

        def all_messages(self) -> list[object]:
            return []

        @property
        def usage(self) -> object:
            return MagicMock()

        @property
        def result(self) -> object:
            return MagicMock(output=reached)

    monkeypatch.setattr(
        _rem_agent_mod.remediation_agent, "iter", lambda *a, **k: _FakeRun()
    )

    result, _usage, _msgs = await run_remediation(
        deps=_deps(mock_git_mcp),
        report=_escalate_report(),
        source_branch="remediation/run-x",
    )
    assert result is reached
    assert result.actions_taken != ["refused_protected_branch"]
