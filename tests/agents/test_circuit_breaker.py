"""Circuit breaker + iteration limit failure-mode tests.

Two layers of coverage:
  1. Unit tests for _CircuitBreaker (pure state machine).
  2. Integration tests for run_orchestration ABORT paths
     (UsageLimitExceeded, UnexpectedModelBehavior, CircuitBreakerTripped) --
     all produce a valid RunRecord with outcome="abort" written to the audit log.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from pydantic_ai.exceptions import UnexpectedModelBehavior, UsageLimitExceeded

os.environ.setdefault("LLM_MODEL_NAME", "test-model")
os.environ.setdefault("LLM_BASE_URL", "http://localhost:1/v1")
os.environ.setdefault("LLM_API_KEY", "sk-test")

from orchestrator import agent as orch_mod
from orchestrator.agent import _CircuitBreaker, run_orchestration
from orchestrator.models import CircuitBreakerTripped, FaultEvent

# --- Unit tests for _CircuitBreaker -----------------------------------


def test_circuit_breaker_does_not_trip_before_three_errors() -> None:
    cb = _CircuitBreaker()
    cb.error()
    cb.error()
    assert cb.consecutive == 2


def test_circuit_breaker_trips_on_third_consecutive_error() -> None:
    cb = _CircuitBreaker()
    cb.error()
    cb.error()
    with pytest.raises(CircuitBreakerTripped):
        cb.error()


def test_circuit_breaker_success_resets_counter() -> None:
    cb = _CircuitBreaker()
    cb.error()
    cb.error()
    cb.success()
    cb.error()
    cb.error()
    assert cb.consecutive == 2


# --- Integration tests for ABORT paths --------------------------------


async def test_run_orchestration_abort_on_usage_limit_exceeded(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_ssh_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setattr(
        orch_mod,
        "run_diagnosis",
        AsyncMock(side_effect=UsageLimitExceeded("request_limit (20) exceeded")),
    )

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        ssh_mcp=mock_ssh_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )
    assert record.outcome == "abort"
    assert record.success_rate is False
    assert record.MTTR_s is None
    written = (tmp_path / "runs" / f"{record.run_id}.json").read_text()
    assert json.loads(written)["outcome"] == "abort"


async def test_run_orchestration_abort_on_unexpected_model_behavior(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_ssh_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setattr(
        orch_mod,
        "run_diagnosis",
        AsyncMock(
            side_effect=UnexpectedModelBehavior("model returned malformed output")
        ),
    )

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        ssh_mcp=mock_ssh_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )
    assert record.outcome == "abort"
    assert record.success_rate is False


async def test_run_orchestration_abort_on_circuit_breaker_tripped(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_ssh_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setattr(
        orch_mod,
        "run_diagnosis",
        AsyncMock(side_effect=CircuitBreakerTripped("3 consecutive MCP errors")),
    )

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        ssh_mcp=mock_ssh_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )
    assert record.outcome == "abort"
