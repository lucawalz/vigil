"""Orchestrator: happy-path + rollback + audit log tests.

Sub-agents (Diagnosis/Remediation/Watchdog) are patched with AsyncMocks so the
test runs without an LLM or cluster. Audit log writes are redirected to tmp_path
via EVAL_RUNS_DIR env override.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("LLM_MODEL_NAME", "test-model")
os.environ.setdefault("LLM_BASE_URL", "http://localhost:1/v1")
os.environ.setdefault("LLM_API_KEY", "sk-test")

from diagnosis.models import DiagnosisReport
from orchestrator import agent as orch_mod
from orchestrator.agent import build_run_id, run_orchestration
from orchestrator.models import FaultEvent, RunRecord
from pydantic_ai.usage import Usage
from remediation.models import RemediationResult
from watchdog.models import HealthSnapshot, WatchdogResult


def _canned_report() -> DiagnosisReport:
    return DiagnosisReport(
        root_cause="wrong image tag",
        root_cause_component="vigil-app:bad-tag-v9",
        severity="high",
        affected_resources=["default/vigil-app"],
        evidence="Failed to pull image vigil-app:bad-tag-v9",
        recommended_action="apply_patch",
        confidence=0.95,
        requires_os_level=False,
    )


def _canned_remediation(success: bool = True) -> RemediationResult:
    return RemediationResult(
        success=success,
        actions_taken=["suspend_kustomization", "apply_patch", "resume_kustomization"],
        tool_calls_count=3,
        destructive_repair=True,
    )


def _canned_baseline() -> HealthSnapshot:
    return HealthSnapshot(
        ready_pods=3,
        total_pods=3,
        endpoints_healthy=True,
        captured_at="2026-04-18T10:00:00Z",
    )


def _watchdog_ok() -> WatchdogResult:
    return WatchdogResult(degraded=False, snapshot=_canned_baseline())


async def test_run_orchestration_happy_path(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_ssh_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    diag_rv = (_canned_report(), Usage(input_tokens=100, output_tokens=50), [])
    rem_rv = (_canned_remediation(), Usage(input_tokens=200, output_tokens=80), [])
    monkeypatch.setattr(orch_mod, "run_diagnosis", AsyncMock(return_value=diag_rv))
    monkeypatch.setattr(
        orch_mod,
        "capture_health_snapshot",
        AsyncMock(return_value=_canned_baseline()),
    )
    monkeypatch.setattr(orch_mod, "run_remediation", AsyncMock(return_value=rem_rv))
    monkeypatch.setattr(
        orch_mod, "run_watchdog", AsyncMock(return_value=_watchdog_ok())
    )

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        ssh_mcp=mock_ssh_mcp,
        nixos_mcp=mock_nixos_mcp,
    )
    assert isinstance(record, RunRecord)
    assert record.outcome == "success"
    assert record.success_rate is True
    assert record.rollback_triggered is False
    assert record.destructive_repair is True
    assert record.total_input_tokens == 300
    assert record.total_output_tokens == 130
    written = (tmp_path / "runs" / f"{record.run_id}.json").read_text()
    assert json.loads(written)["run_id"] == record.run_id
    index_lines = (tmp_path / "runs_index.jsonl").read_text().strip().splitlines()
    assert len(index_lines) == 1
    assert json.loads(index_lines[0])["run_id"] == record.run_id


async def test_run_orchestration_triggers_rollback_on_watchdog_degraded(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_ssh_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    diag_rv = (_canned_report(), Usage(input_tokens=50, output_tokens=20), [])
    rem_rv = (_canned_remediation(), Usage(input_tokens=100, output_tokens=30), [])
    monkeypatch.setattr(orch_mod, "run_diagnosis", AsyncMock(return_value=diag_rv))
    monkeypatch.setattr(
        orch_mod,
        "capture_health_snapshot",
        AsyncMock(return_value=_canned_baseline()),
    )
    monkeypatch.setattr(orch_mod, "run_remediation", AsyncMock(return_value=rem_rv))
    degraded_snap = HealthSnapshot(
        ready_pods=0,
        total_pods=3,
        endpoints_healthy=False,
        captured_at="2026-04-18T10:00:05Z",
    )
    degraded_rv = WatchdogResult(degraded=True, snapshot=degraded_snap)
    monkeypatch.setattr(orch_mod, "run_watchdog", AsyncMock(return_value=degraded_rv))
    mock_kubectl_mcp.direct_call_tool = AsyncMock(
        return_value={"content": "rolled back"}
    )

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        ssh_mcp=mock_ssh_mcp,
        nixos_mcp=mock_nixos_mcp,
    )
    assert record.rollback_triggered is True
    assert record.rollback_success is True
    calls = [
        c
        for c in mock_kubectl_mcp.direct_call_tool.call_args_list
        if c.args and c.args[0] == "rollout_undo"
    ]
    assert len(calls) >= 1


async def test_run_orchestration_record_has_all_eval_07_fields(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_ssh_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    diag_rv = (_canned_report(), Usage(input_tokens=100, output_tokens=50), [])
    rem_rv = (_canned_remediation(), Usage(input_tokens=200, output_tokens=80), [])
    monkeypatch.setattr(orch_mod, "run_diagnosis", AsyncMock(return_value=diag_rv))
    monkeypatch.setattr(
        orch_mod,
        "capture_health_snapshot",
        AsyncMock(return_value=_canned_baseline()),
    )
    monkeypatch.setattr(orch_mod, "run_remediation", AsyncMock(return_value=rem_rv))
    monkeypatch.setattr(
        orch_mod, "run_watchdog", AsyncMock(return_value=_watchdog_ok())
    )

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        ssh_mcp=mock_ssh_mcp,
        nixos_mcp=mock_nixos_mcp,
    )
    assert record.total_input_tokens == 300
    assert record.total_output_tokens == 130
    required = {
        "success_rate",
        "diagnosis_accuracy",
        "MTTR_s",
        "destructive_repair",
        "rollback_triggered",
        "rollback_success",
        "total_input_tokens",
        "total_output_tokens",
        "total_tool_calls",
        "iteration_count",
        "autonomy_level",
    }
    present = set(RunRecord.model_fields.keys())
    assert required.issubset(present)
    assert record.MTTR_s is not None
    assert record.MTTR_s >= 0.0


async def test_run_orchestration_run_id_format(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_ssh_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setattr(
        orch_mod,
        "run_diagnosis",
        AsyncMock(return_value=(_canned_report(), Usage(), [])),
    )
    monkeypatch.setattr(
        orch_mod,
        "capture_health_snapshot",
        AsyncMock(return_value=_canned_baseline()),
    )
    monkeypatch.setattr(
        orch_mod,
        "run_remediation",
        AsyncMock(return_value=(_canned_remediation(), Usage(), [])),
    )
    monkeypatch.setattr(
        orch_mod, "run_watchdog", AsyncMock(return_value=_watchdog_ok())
    )

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        ssh_mcp=mock_ssh_mcp,
        nixos_mcp=mock_nixos_mcp,
    )
    pattern = r"^k8s-1_seed-\d{8}T\d{6}Z_test-model_[0-9a-f]{7}$"
    assert re.match(pattern, record.run_id), (
        f"run_id {record.run_id!r} does not match expected pattern"
    )


def test_build_run_id_uses_explicit_integer_seed() -> None:
    run_id, seed_str, sha7 = build_run_id("k8s-1", "claude-sonnet-4-5", seed=3)
    assert seed_str == "3"
    assert re.match(r"^k8s-1_3_claude-sonnet-4-5_[a-f0-9]{7}$", run_id), run_id


def test_build_run_id_seed_kwarg_is_stringified() -> None:
    _, seed_str, _ = build_run_id("k8s-2", "m1", seed=7)
    assert seed_str == "7"


def test_build_run_id_seed_none_falls_back_to_timestamp() -> None:
    _, seed_str, _ = build_run_id("k8s-1", "m1")
    assert seed_str.startswith("seed-")
    assert re.match(r"^seed-\d{8}T\d{6}Z$", seed_str), seed_str


def _make_run_record(**overrides) -> RunRecord:
    defaults = dict(
        run_id="k8s-1_1_test-model_abc1234",
        scenario="k8s-1",
        seed="1",
        model="test-model",
        git_sha7="abc1234",
        started_at="2026-04-24T00:00:00Z",
        ended_at="2026-04-24T00:01:00Z",
        outcome="success",
        success_rate=True,
        diagnosis_accuracy=None,
        MTTR_s=60.0,
        destructive_repair=False,
        rollback_triggered=False,
        rollback_success=None,
        total_input_tokens=100,
        total_output_tokens=50,
        total_tool_calls=3,
        iteration_count=1,
        autonomy_level="full",
        actions_taken=[],
    )
    defaults.update(overrides)
    return RunRecord(**defaults)


def test_run_record_has_actions_taken_and_model_version_fields() -> None:
    assert "actions_taken" in RunRecord.model_fields
    assert "model_version" in RunRecord.model_fields

    record = _make_run_record(
        actions_taken=["suspend_kustomization", "apply_patch"],
        model_version="qwen3-coder-next:cloud",
    )
    data = json.loads(record.model_dump_json())
    assert data["actions_taken"] == ["suspend_kustomization", "apply_patch"]
    assert data["model_version"] == "qwen3-coder-next:cloud"


async def test_run_orchestration_forwards_seed_to_run_id(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_ssh_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setattr(
        orch_mod,
        "run_diagnosis",
        AsyncMock(return_value=(_canned_report(), Usage(), [])),
    )
    monkeypatch.setattr(
        orch_mod,
        "capture_health_snapshot",
        AsyncMock(return_value=_canned_baseline()),
    )
    monkeypatch.setattr(
        orch_mod,
        "run_remediation",
        AsyncMock(return_value=(_canned_remediation(), Usage(), [])),
    )
    monkeypatch.setattr(
        orch_mod, "run_watchdog", AsyncMock(return_value=_watchdog_ok())
    )
    spy = MagicMock(wraps=build_run_id)
    monkeypatch.setattr(orch_mod, "build_run_id", spy)

    await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        ssh_mcp=mock_ssh_mcp,
        nixos_mcp=mock_nixos_mcp,
        scenario="k8s-3",
        seed=5,
    )
    spy.assert_called_once()
    _, kwargs = spy.call_args
    assert kwargs.get("seed") == 5
