"""Remediation agent structural + contract tests.

Asserts flux_suspend-first ordering at the prompt level and that the
toolset scope excludes ssh_mcp.
"""

from __future__ import annotations

import inspect
import os

os.environ.setdefault("LLM_MODEL_NAME", "test-model")
os.environ.setdefault("LLM_BASE_URL", "http://localhost:1/v1")
os.environ.setdefault("LLM_API_KEY", "sk-test")

import remediation.agent as _rem_agent_mod
from diagnosis.models import DiagnosisReport
from pydantic_ai import Agent
from remediation.agent import remediation_agent, run_remediation
from remediation.models import RemediationResult


def test_remediation_agent_is_agent_instance() -> None:
    assert isinstance(remediation_agent, Agent)


def test_run_remediation_is_coroutine() -> None:
    assert inspect.iscoroutinefunction(run_remediation)


def test_run_remediation_toolsets_exclude_ssh() -> None:
    """Remediation scope is kubectl+flux+nixos only, no ssh."""
    source = inspect.getsource(run_remediation)
    assert "toolsets=[deps.kubectl_mcp, deps.flux_mcp, deps.nixos_mcp]" in source
    assert "ssh_mcp" not in source


def test_run_remediation_enforces_usage_limit() -> None:
    """20-request ceiling applies to Remediation loop too."""
    source = inspect.getsource(run_remediation)
    assert "UsageLimits(request_limit=20)" in source


def test_remediation_prompt_mandates_flux_suspend_first() -> None:
    """suspend_kustomization must be the first tool call."""
    mod_source = inspect.getsource(_rem_agent_mod)
    assert "suspend_kustomization" in mod_source
    assert "resume_kustomization" in mod_source
    # At least one uppercase-emphasised ordering word must appear.
    has_emphasis = any(
        kw in mod_source for kw in ("FIRST", "MANDATORY", "MUST")
    )
    assert has_emphasis, "Prompt must emphasise suspend_kustomization ordering"


def test_remediation_prompt_references_affected_resources() -> None:
    """Per-resource guard requires prompt to name the Kustomization."""
    mod_source = inspect.getsource(_rem_agent_mod)
    assert "affected_resources" in mod_source


def test_run_remediation_signature() -> None:
    sig = inspect.signature(run_remediation)
    params = list(sig.parameters.values())
    assert len(params) == 2
    assert params[0].name == "deps"
    assert params[1].name == "report"
    # Second param annotation is DiagnosisReport (class or forward-ref string).
    ann_report = params[1].annotation
    assert ann_report is DiagnosisReport or (
        isinstance(ann_report, str) and "DiagnosisReport" in ann_report
    )


def test_remediation_result_fields_stable() -> None:
    """Guard: RemediationResult schema must not drift."""
    fields = set(RemediationResult.model_fields.keys())
    assert fields == {
        "success",
        "actions_taken",
        "tool_calls_count",
        "destructive_repair",
    }


def test_run_remediation_returns_tuple_with_usage() -> None:
    """Orchestrator needs usage tuple for token aggregation."""
    source = inspect.getsource(run_remediation)
    assert "result.usage()" in source
    assert "return result.output, result.usage()" in source
