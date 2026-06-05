"""Per-attempt remediation branch identity tests.

Verifies the orchestrator derives a deterministic, attempt-scoped branch token
and that the resulting branch name matches the git-mcp server's prefix.
"""

from __future__ import annotations

import inspect
import os

os.environ.setdefault("LLM_MODEL_NAME", "test-model")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:1/v1")
os.environ.setdefault("OLLAMA_API_KEY", "sk-test")

import remediation.agent as _rem_agent_mod
from orchestrator.agent import _REMEDIATION_BRANCH_PREFIX, _attempt_branch_token


def test_attempt_branch_token_appends_attempt_suffix() -> None:
    assert _attempt_branch_token("os-1_1_qwen_abc", 2) == "os-1_1_qwen_abc-attempt-2"


def test_attempt_branch_token_is_unique_per_attempt() -> None:
    run_id = "k8s-1_42_model_abc1234"
    tokens = {_attempt_branch_token(run_id, attempt) for attempt in range(1, 4)}
    assert len(tokens) == 3


def test_branch_name_matches_git_mcp_prefix() -> None:
    run_id = "k8s-1_42_model_abc1234"
    branch = _REMEDIATION_BRANCH_PREFIX + _attempt_branch_token(run_id, 3)
    assert branch == f"remediation/run-{run_id}-attempt-3"


def test_run_remediation_accepts_agent_branch_param() -> None:
    sig = inspect.signature(_rem_agent_mod.run_remediation)
    assert "agent_branch" in sig.parameters


def test_task_string_records_provided_agent_branch() -> None:
    source = inspect.getsource(_rem_agent_mod.run_remediation)
    assert "agent_branch = {agent_branch}" in source
