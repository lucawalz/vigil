"""Remediation branch identity tests."""

from __future__ import annotations

import inspect
import os

os.environ.setdefault("LLM_MODEL_NAME", "test-model")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:1/v1")
os.environ.setdefault("OLLAMA_API_KEY", "sk-test")

import remediation.agent as _rem_agent_mod


def test_run_remediation_accepts_agent_branch_param() -> None:
    sig = inspect.signature(_rem_agent_mod.run_remediation)
    assert "agent_branch" in sig.parameters


def test_task_string_records_provided_agent_branch() -> None:
    source = inspect.getsource(_rem_agent_mod.run_remediation)
    assert "agent_branch = {agent_branch}" in source
