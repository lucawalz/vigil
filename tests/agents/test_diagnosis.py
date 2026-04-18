"""Diagnosis agent configuration and run_diagnosis wiring tests.

These tests verify structural contracts (agent construction, toolset scope,
usage limits, prompt content) without running the live LLM.
"""

from __future__ import annotations

import inspect
import os

# Provide test env vars BEFORE importing diagnosis.agent (build_model() reads them).
os.environ.setdefault("LLM_MODEL_NAME", "test-model")
os.environ.setdefault("LLM_BASE_URL", "http://localhost:1/v1")
os.environ.setdefault("LLM_API_KEY", "sk-test")

import diagnosis.agent as _diag_module
from diagnosis.agent import diagnosis_agent, run_diagnosis
from diagnosis.models import DiagnosisDeps, DiagnosisReport
from pydantic_ai import Agent


def test_diagnosis_agent_is_agent_instance() -> None:
    assert isinstance(diagnosis_agent, Agent)


def test_diagnosis_agent_output_type_is_diagnosis_report() -> None:
    source = inspect.getsource(_diag_module)
    assert "output_type=DiagnosisReport" in source
    assert DiagnosisReport.__name__ == "DiagnosisReport"


def test_run_diagnosis_is_coroutine() -> None:
    assert inspect.iscoroutinefunction(run_diagnosis)


def test_run_diagnosis_uses_only_diagnosis_scoped_toolsets() -> None:
    """Diagnosis must receive only kubectl+ssh+nixos MCP clients."""
    source = inspect.getsource(run_diagnosis)
    assert "toolsets=[deps.kubectl_mcp, deps.ssh_mcp, deps.nixos_mcp]" in source
    assert "flux_mcp" not in source


def test_run_diagnosis_enforces_usage_limit_20() -> None:
    """20-iteration ceiling via UsageLimits(request_limit=20)."""
    source = inspect.getsource(run_diagnosis)
    assert "UsageLimits(request_limit=20)" in source


def test_diagnosis_system_prompt_forbids_symptom_naming() -> None:
    """System prompt must never name a symptom as root cause."""
    source = inspect.getsource(_diag_module)
    has_symptom_clause = any(
        term in source for term in ("CrashLoopBackOff", "ImagePullBackOff", "OOMKilled")
    )
    assert has_symptom_clause, "System prompt must forbid K8s symptoms as root causes"


def test_run_diagnosis_signature_accepts_diagnosis_deps() -> None:
    """run_diagnosis(deps: DiagnosisDeps, fault: FaultEvent) -> tuple."""
    sig = inspect.signature(run_diagnosis)
    params = list(sig.parameters.values())
    assert len(params) == 2
    assert params[0].name == "deps"
    ann = params[0].annotation
    assert ann is DiagnosisDeps or (isinstance(ann, str) and "DiagnosisDeps" in ann)


def test_run_diagnosis_returns_tuple_with_usage() -> None:
    """Orchestrator needs usage tuple for token aggregation."""
    source = inspect.getsource(run_diagnosis)
    assert "result.usage()" in source
    assert "return result.output, result.usage()" in source
