"""Orchestrator: happy-path + rollback + audit log tests.

Sub-agents (Diagnosis/Remediation/Watchdog) are patched with AsyncMocks so the
test runs without an LLM or cluster. Audit log writes are redirected to tmp_path
via EVAL_RUNS_DIR env override.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("LLM_MODEL_NAME", "test-model")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:1/v1")
os.environ.setdefault("OLLAMA_API_KEY", "sk-test")

from diagnosis.models import DiagnosisOutputRetryExhausted, DiagnosisReport
from orchestrator import agent as orch_mod
from orchestrator.agent import (
    _RUN_LOCK,
    _issue_rollback,
    _score_diagnosis_accuracy,
    build_run_id,
    run_orchestration,
)
from orchestrator.models import CircuitBreakerTripped, FaultEvent, RunRecord
from pydantic_ai.exceptions import UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.usage import RunUsage
from remediation.models import RemediationOutputRetryExhausted, RemediationResult
from watchdog.models import HealthSnapshot, WatchdogResult

_ACTION_DRIFT: dict[str, str] = {
    "flux_reconcile": "live_only_drift",
    "nixos_rebuild": "live_only_drift",
    "git_commit_k8s": "declared_drift",
    "git_commit_nix": "declared_drift",
    "escalate": "no_drift",
}


def _canned_report() -> DiagnosisReport:
    return DiagnosisReport(
        root_cause="wrong image tag",
        root_cause_component="vigil-app:bad-tag-v9",
        severity="high",
        affected_resources=["default/vigil-app"],
        evidence="Failed to pull image vigil-app:bad-tag-v9",
        drift_classification="declared_drift",
        recommended_action="git_commit_k8s",
        confidence=0.95,
        manifest_path="infra/overlays/hetzner/kubernetes/clusters/hetzner/apps/vigil-app.yaml",
        resource_kind="Deployment",
        resource_name="vigil-app",
        resource_namespace="default",
        patch_body=(
            "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: vigil-app\n"
        ),
    )


def _canned_report_with_action(
    action: str, target_host: str | None = None
) -> DiagnosisReport:
    return DiagnosisReport(
        root_cause="test fault",
        root_cause_component="vigil-app",
        severity="high",
        affected_resources=["default/vigil-app"],
        evidence="test evidence",
        drift_classification=_ACTION_DRIFT[action],
        recommended_action=action,
        confidence=0.9,
        target_host=target_host,
    )


def _canned_remediation(success: bool = True) -> RemediationResult:
    return RemediationResult(
        success=success,
        actions_taken=[
            "create_branch",
            "write_manifest",
            "commit_files",
            "push_branch",
            "create_pr",
            "wait_for_gate",
            "reconcile_kustomization",
        ],
        tool_calls_count=7,
        mutation_attempted=True,
        merge_commit_sha="deadbeef1234567",
        agent_branch="remediation/run-k8s-1",
        agent_commits=["deadbeef1234567"],
        gate_status="merged",
    )


def _canned_baseline() -> HealthSnapshot:
    return HealthSnapshot(
        workload_found=True,
        generation=1,
        observed_generation=1,
        spec_replicas=3,
        ready_replicas=3,
        updated_replicas=3,
        available_replicas=3,
        available_condition=True,
        progressing_ok=True,
        ready_pods=3,
        total_pods=3,
        flux_ready=True,
        captured_at="2026-04-18T10:00:00Z",
    )


def _degraded_snapshot() -> HealthSnapshot:
    return HealthSnapshot(
        workload_found=True,
        generation=1,
        observed_generation=1,
        spec_replicas=3,
        ready_replicas=0,
        updated_replicas=3,
        available_replicas=0,
        available_condition=False,
        progressing_ok=True,
        ready_pods=0,
        total_pods=3,
        flux_ready=True,
        captured_at="2026-04-18T10:00:05Z",
    )


def _watchdog_ok() -> WatchdogResult:
    return WatchdogResult(degraded=False, snapshot=_canned_baseline(), reason="healthy")


async def test_run_orchestration_happy_path(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    diag_rv = (_canned_report(), RunUsage(input_tokens=100, output_tokens=50), [])
    rem_rv = (_canned_remediation(), RunUsage(input_tokens=200, output_tokens=80), [])
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
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )
    assert isinstance(record, RunRecord)
    assert record.outcome == "success"
    assert record.success_rate is True
    assert record.rollback_triggered is False
    assert record.destructive_repair is False
    assert record.total_input_tokens == 300
    assert record.total_output_tokens == 130
    assert record.agent_branch == "remediation/run-k8s-1"
    assert record.agent_commits == ["deadbeef1234567"]
    assert record.gate_status == "merged"
    assert record.merge_commit_sha == "deadbeef1234567"
    written = (tmp_path / "runs" / f"{record.run_id}.json").read_text()
    assert json.loads(written)["run_id"] == record.run_id
    index_lines = (tmp_path / "runs_index.jsonl").read_text().strip().splitlines()
    assert len(index_lines) == 1
    assert json.loads(index_lines[0])["run_id"] == record.run_id


async def test_run_orchestration_captures_usage_on_remediation_retry_exhaustion(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    diag_rv = (_canned_report(), RunUsage(input_tokens=100, output_tokens=50), [])
    monkeypatch.setattr(orch_mod, "run_diagnosis", AsyncMock(return_value=diag_rv))
    monkeypatch.setattr(
        orch_mod,
        "capture_health_snapshot",
        AsyncMock(return_value=_canned_baseline()),
    )
    monkeypatch.setattr(
        orch_mod,
        "run_remediation",
        AsyncMock(
            side_effect=RemediationOutputRetryExhausted(
                RunUsage(input_tokens=200, output_tokens=80),
                [],
                UnexpectedModelBehavior("exceeded max retries count of 3"),
            )
        ),
    )
    monkeypatch.setattr(
        orch_mod, "run_watchdog", AsyncMock(return_value=_watchdog_ok())
    )

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )
    assert record.outcome == "abort"
    assert record.setup_error is not None
    assert "retry_exhausted:remediation" in record.setup_error
    assert record.total_input_tokens == 300
    assert record.total_output_tokens == 130


async def test_run_orchestration_aborts_on_indeterminate_baseline(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from watchdog.models import HealthSnapshotUnavailable

    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    run_watchdog_mock = AsyncMock(return_value=_watchdog_ok())
    run_diagnosis_mock = AsyncMock()
    monkeypatch.setattr(orch_mod, "run_diagnosis", run_diagnosis_mock)
    monkeypatch.setattr(
        orch_mod,
        "capture_health_snapshot",
        AsyncMock(side_effect=HealthSnapshotUnavailable("unparseable get_pods")),
    )
    monkeypatch.setattr(orch_mod, "run_watchdog", run_watchdog_mock)

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )
    assert record.outcome == "abort"
    assert record.success_rate is False
    assert record.setup_error == "baseline_unavailable"
    run_diagnosis_mock.assert_not_awaited()
    run_watchdog_mock.assert_not_awaited()
    written = (tmp_path / "runs" / f"{record.run_id}.json").read_text()
    assert json.loads(written)["setup_error"] == "baseline_unavailable"


async def test_run_orchestration_triggers_rollback_on_watchdog_degraded(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    diag_rv = (_canned_report(), RunUsage(input_tokens=50, output_tokens=20), [])
    rem_rv = (_canned_remediation(), RunUsage(input_tokens=100, output_tokens=30), [])
    monkeypatch.setattr(orch_mod, "run_diagnosis", AsyncMock(return_value=diag_rv))
    monkeypatch.setattr(
        orch_mod,
        "capture_health_snapshot",
        AsyncMock(return_value=_canned_baseline()),
    )
    monkeypatch.setattr(orch_mod, "run_remediation", AsyncMock(return_value=rem_rv))
    degraded_snap = _degraded_snapshot()
    degraded_rv = WatchdogResult(degraded=True, snapshot=degraded_snap)
    monkeypatch.setattr(orch_mod, "run_watchdog", AsyncMock(return_value=degraded_rv))
    mock_git_mcp.direct_call_tool = AsyncMock(
        return_value={"content": "reverted: cafebabe"}
    )
    mock_flux_mcp.direct_call_tool = AsyncMock(
        side_effect=lambda tool, args: (
            {"content": '{"found": true, "ready": true}'}
            if tool == "get_kustomization_status"
            else {"content": "reconciled"}
        )
    )

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )
    assert record.rollback_triggered is True
    assert record.rollback_success is True
    calls = [
        c
        for c in mock_git_mcp.direct_call_tool.call_args_list
        if c.args and c.args[0] == "revert_commit"
    ]
    assert len(calls) >= 1
    assert record.outcome in ("rollback_succeeded", "rollback_failed")


async def test_run_orchestration_record_has_all_eval_07_fields(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    diag_rv = (_canned_report(), RunUsage(input_tokens=100, output_tokens=50), [])
    rem_rv = (_canned_remediation(), RunUsage(input_tokens=200, output_tokens=80), [])
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
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
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
        "agent_branch",
        "agent_commits",
        "gate_status",
    }
    present = set(RunRecord.model_fields.keys())
    assert required.issubset(present)
    assert record.MTTR_s is not None
    assert record.MTTR_s >= 0.0


async def test_merged_run_records_merge_commit_sha(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    diag_rv = (_canned_report(), RunUsage(input_tokens=100, output_tokens=50), [])
    rem_rv = (_canned_remediation(), RunUsage(input_tokens=200, output_tokens=80), [])
    monkeypatch.setattr(orch_mod, "run_diagnosis", AsyncMock(return_value=diag_rv))
    monkeypatch.setattr(
        orch_mod, "capture_health_snapshot", AsyncMock(return_value=_canned_baseline())
    )
    monkeypatch.setattr(orch_mod, "run_remediation", AsyncMock(return_value=rem_rv))
    monkeypatch.setattr(
        orch_mod, "run_watchdog", AsyncMock(return_value=_watchdog_ok())
    )

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )

    assert "merge_commit_sha" in RunRecord.model_fields
    assert record.merge_commit_sha == "deadbeef1234567"
    written = json.loads((tmp_path / "runs" / f"{record.run_id}.json").read_text())
    assert written["merge_commit_sha"] == "deadbeef1234567"


async def test_run_orchestration_run_id_format(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setattr(
        orch_mod,
        "run_diagnosis",
        AsyncMock(return_value=(_canned_report(), RunUsage(), [])),
    )
    monkeypatch.setattr(
        orch_mod,
        "capture_health_snapshot",
        AsyncMock(return_value=_canned_baseline()),
    )
    monkeypatch.setattr(
        orch_mod,
        "run_remediation",
        AsyncMock(return_value=(_canned_remediation(), RunUsage(), [])),
    )
    monkeypatch.setattr(
        orch_mod, "run_watchdog", AsyncMock(return_value=_watchdog_ok())
    )

    monkeypatch.delenv("GIT_SHA7", raising=False)
    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
        model_name="test-model",
    )
    pattern = r"^k8s-1_seed-\d{8}T\d{6}Z-[a-f0-9]{8}_test-model_[0-9a-f]{7}$"
    assert re.match(pattern, record.run_id), (
        f"run_id {record.run_id!r} does not match expected pattern"
    )


def test_build_run_id_uses_explicit_integer_seed() -> None:
    run_id, seed_str, sha7 = build_run_id("k8s-1", "claude-sonnet-4-6", seed=3)
    assert seed_str == "3"
    assert re.match(r"^k8s-1_3_claude-sonnet-4-6_[a-f0-9]{7}$", run_id), run_id


def test_build_run_id_seed_kwarg_is_stringified() -> None:
    _, seed_str, _ = build_run_id("k8s-2", "m1", seed=7)
    assert seed_str == "7"


def test_build_run_id_seed_none_falls_back_to_timestamp() -> None:
    _, seed_str, _ = build_run_id("k8s-1", "m1")
    assert seed_str.startswith("seed-")
    assert re.match(r"^seed-\d{8}T\d{6}Z-[a-f0-9]{8}$", seed_str), seed_str


def test_build_run_id_seeded_format_is_stable() -> None:
    first = build_run_id("k8s-1", "claude-sonnet-4-6", seed=3)
    second = build_run_id("k8s-1", "claude-sonnet-4-6", seed=3)
    assert first == second


def test_build_run_id_seedless_runs_are_distinct() -> None:
    first_id, _, _ = build_run_id("k8s-1", "m1")
    second_id, _, _ = build_run_id("k8s-1", "m1")
    assert first_id != second_id


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
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setattr(
        orch_mod,
        "run_diagnosis",
        AsyncMock(return_value=(_canned_report(), RunUsage(), [])),
    )
    monkeypatch.setattr(
        orch_mod,
        "capture_health_snapshot",
        AsyncMock(return_value=_canned_baseline()),
    )
    monkeypatch.setattr(
        orch_mod,
        "run_remediation",
        AsyncMock(return_value=(_canned_remediation(), RunUsage(), [])),
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
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
        scenario="k8s-3",
        seed=5,
    )
    spy.assert_called_once()
    _, kwargs = spy.call_args
    assert kwargs.get("seed") == 5


def test_build_run_id_uses_git_sha7_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_SHA7", "abc1234")
    import subprocess as subprocess_mod

    monkeypatch.setattr(
        subprocess_mod,
        "check_output",
        MagicMock(side_effect=AssertionError("git should not be called")),
    )
    run_id, _, sha7 = build_run_id("k8s-1", "m", seed=1)
    assert sha7 == "abc1234"
    assert run_id.endswith("_abc1234")


def test_build_run_id_falls_back_to_subprocess_when_env_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GIT_SHA7", raising=False)
    run_id, _, sha7 = build_run_id("k8s-1", "m", seed=1)
    assert re.match(r"^[0-9a-f]{7}$", sha7), f"expected 7-hex sha7, got {sha7!r}"


def test_build_run_id_falls_back_to_0000000_when_env_empty_and_git_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GIT_SHA7", "")
    import subprocess as subprocess_mod

    monkeypatch.setattr(
        subprocess_mod,
        "check_output",
        MagicMock(side_effect=FileNotFoundError("git not found")),
    )
    _, _, sha7 = build_run_id("k8s-1", "m", seed=1)
    assert sha7 == "0000000"


def _canned_diagnosis_context():
    from diagnosis.context import DiagnosisContext

    return DiagnosisContext(
        source_branch="main",
        manifest_path="apps/vigil-app.yaml",
        live_yaml="live: yaml",
        declared_yaml="declared: yaml",
        diff="",
    )


def _run_orch_setup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.delenv("GIT_SHA7", raising=False)
    monkeypatch.setattr(
        orch_mod,
        "build_diagnosis_context",
        AsyncMock(return_value=_canned_diagnosis_context()),
    )
    diag_rv = (_canned_report(), RunUsage(input_tokens=100, output_tokens=50), [])
    rem_rv = (_canned_remediation(), RunUsage(input_tokens=200, output_tokens=80), [])
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


async def test_concurrent_run_orchestration_calls_do_not_overlap(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _run_orch_setup(monkeypatch, tmp_path)
    active = 0
    max_active = 0

    async def _diagnosis_with_overlap_check(*_args, **_kwargs):
        nonlocal active, max_active
        assert _RUN_LOCK.locked()
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0)
        active -= 1
        return (_canned_report(), RunUsage(input_tokens=100, output_tokens=50), [])

    monkeypatch.setattr(
        orch_mod, "run_diagnosis", AsyncMock(side_effect=_diagnosis_with_overlap_check)
    )

    async def _launch():
        return await run_orchestration(
            sample_fault_event,
            kubectl_mcp=mock_kubectl_mcp,
            flux_mcp=mock_flux_mcp,
            nixos_mcp=mock_nixos_mcp,
            git_mcp=mock_git_mcp,
        )

    records = await asyncio.gather(_launch(), _launch())
    assert max_active == 1
    assert all(isinstance(r, RunRecord) for r in records)
    assert records[0].run_id != records[1].run_id


async def test_run_record_has_actions_taken_populated(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenarios_dir = tmp_path / "scenarios" / "k8s-1"
    scenarios_dir.mkdir(parents=True)
    (scenarios_dir / "scenario.yaml").write_text("expected_action: git_commit_k8s\n")
    monkeypatch.setenv("VIGIL_SCENARIOS_DIR", str(tmp_path / "scenarios"))
    _run_orch_setup(monkeypatch, tmp_path)
    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )
    assert record.actions_taken == []
    assert record.forbidden_action_violations == []
    assert record.diagnosis_accuracy is not None


async def test_run_record_has_model_version_populated(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _run_orch_setup(monkeypatch, tmp_path)
    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
        model_name="qwen3-coder-next:cloud",
    )
    assert record.model_version == "qwen3-coder-next:cloud"


async def test_diagnosis_accuracy_scored_true_for_k8s_scenario(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenarios_dir = tmp_path / "scenarios" / "k8s-1"
    scenarios_dir.mkdir(parents=True)
    (scenarios_dir / "scenario.yaml").write_text("expected_action: flux_reconcile\n")
    monkeypatch.setenv("VIGIL_SCENARIOS_DIR", str(tmp_path / "scenarios"))
    _run_orch_setup(monkeypatch, tmp_path)
    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
        scenario="k8s-1",
    )
    assert record.diagnosis_accuracy is not None


async def test_diagnosis_accuracy_scored_false_for_os_scenario_missed_escalation(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenarios_dir = tmp_path / "scenarios" / "os-1"
    scenarios_dir.mkdir(parents=True)
    (scenarios_dir / "scenario.yaml").write_text("expected_action: nixos_rebuild\n")
    monkeypatch.setenv("VIGIL_SCENARIOS_DIR", str(tmp_path / "scenarios"))
    _run_orch_setup(monkeypatch, tmp_path)
    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
        scenario="os-1",
    )
    assert record.diagnosis_accuracy is False


async def test_diagnosis_accuracy_none_when_scenario_yaml_absent(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIGIL_SCENARIOS_DIR", str(tmp_path / "scenarios"))
    _run_orch_setup(monkeypatch, tmp_path)
    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
        scenario="nonexistent-scenario",
    )
    assert record.diagnosis_accuracy is None


async def test_abort_record_also_carries_actions_taken_and_model_version(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setattr(
        orch_mod,
        "run_diagnosis",
        AsyncMock(side_effect=UsageLimitExceeded("limit")),
    )
    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
        model_name="qwen3-coder-next:cloud",
    )
    assert record.outcome == "abort"
    assert record.actions_taken == []
    assert record.model_version == "qwen3-coder-next:cloud"
    assert record.agent_branch is None
    assert record.agent_commits is None
    assert record.gate_status is None
    assert record.forbidden_action_violations == []


async def test_runs_index_written_on_abort_path_usage_limit(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setattr(
        orch_mod,
        "run_diagnosis",
        AsyncMock(side_effect=UsageLimitExceeded("limit")),
    )
    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )
    index = tmp_path / "runs_index.jsonl"
    assert index.exists()
    lines = index.read_text().strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["outcome"] == "abort"
    assert json.loads(lines[0])["run_id"] == record.run_id


async def test_runs_index_written_on_abort_path_circuit_breaker(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
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
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )
    index = tmp_path / "runs_index.jsonl"
    assert index.exists()
    lines = index.read_text().strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["outcome"] == "abort"
    assert json.loads(lines[0])["run_id"] == record.run_id


async def test_abort_record_preserves_setup_error_reason(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setattr(
        orch_mod,
        "capture_health_snapshot",
        AsyncMock(return_value=_canned_baseline()),
    )
    monkeypatch.setattr(
        orch_mod,
        "run_diagnosis",
        AsyncMock(
            side_effect=DiagnosisOutputRetryExhausted(
                RunUsage(input_tokens=1234, output_tokens=56),
                [],
                UnexpectedModelBehavior(
                    "Tool 'read_file' exceeded max retries count of 3"
                ),
            )
        ),
    )
    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )
    assert record.outcome == "abort"
    assert record.setup_error is not None
    assert "retry_exhausted:diagnosis" in record.setup_error
    assert "read_file" in record.setup_error
    assert record.total_input_tokens == 1234
    assert record.total_output_tokens == 56


async def test_runs_index_path_resolution_uses_parent_of_runs_dir(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runs_dir = tmp_path / "custom" / "runs"
    monkeypatch.setenv("EVAL_RUNS_DIR", str(runs_dir))
    _run_orch_setup(monkeypatch, tmp_path)
    monkeypatch.setenv("EVAL_RUNS_DIR", str(runs_dir))
    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )
    assert (tmp_path / "custom" / "runs_index.jsonl").exists()
    assert record.outcome == "success"


def test_score_diagnosis_accuracy_boundary_os_escalation_is_false(
    tmp_path: Path,
) -> None:
    scenario_dir = tmp_path / "boundary-2"
    scenario_dir.mkdir(parents=True)
    (scenario_dir / "scenario.yaml").write_text("expected_action: nixos_rebuild\n")
    report = SimpleNamespace(recommended_action="nixos_rebuild")

    import os as _os

    orig = _os.environ.get("VIGIL_SCENARIOS_DIR")
    _os.environ["VIGIL_SCENARIOS_DIR"] = str(tmp_path)
    try:
        result = _score_diagnosis_accuracy("boundary-2", report)
    finally:
        if orig is None:
            _os.environ.pop("VIGIL_SCENARIOS_DIR", None)
        else:
            _os.environ["VIGIL_SCENARIOS_DIR"] = orig

    assert result is True


def test_orchestrator_constants_have_correct_defaults() -> None:
    assert orch_mod.ORCHESTRATOR_RUN_TIMEOUT_S == 1800.0
    assert orch_mod.REMEDIATION_TIMEOUT_S == 600.0
    assert orch_mod._MAX_DIAGNOSIS_ATTEMPTS == 3


def _watchdog_degraded() -> WatchdogResult:
    return WatchdogResult(
        degraded=True, snapshot=_degraded_snapshot(), reason="deadline_reached"
    )


async def test_outcome_rollback_succeeded(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    diag_rv = (_canned_report(), RunUsage(input_tokens=50, output_tokens=20), [])
    rem_rv = (_canned_remediation(), RunUsage(input_tokens=100, output_tokens=30), [])
    monkeypatch.setattr(orch_mod, "run_diagnosis", AsyncMock(return_value=diag_rv))
    monkeypatch.setattr(
        orch_mod,
        "capture_health_snapshot",
        AsyncMock(return_value=_canned_baseline()),
    )
    monkeypatch.setattr(orch_mod, "run_remediation", AsyncMock(return_value=rem_rv))
    degraded_snap = _degraded_snapshot()
    degraded_rv = WatchdogResult(degraded=True, snapshot=degraded_snap)
    monkeypatch.setattr(orch_mod, "run_watchdog", AsyncMock(return_value=degraded_rv))
    mock_git_mcp.direct_call_tool = AsyncMock(
        return_value={"content": "reverted: cafebabe"}
    )
    mock_flux_mcp.direct_call_tool = AsyncMock(
        side_effect=lambda tool, args: (
            {"content": '{"found": true, "ready": true}'}
            if tool == "get_kustomization_status"
            else {"content": "ok"}
        )
    )

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )
    assert record.outcome == "rollback_succeeded"
    assert record.rollback_triggered is True
    assert record.rollback_success is True


async def test_outcome_rollback_failed(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    diag_rv = (_canned_report(), RunUsage(input_tokens=50, output_tokens=20), [])
    rem_rv = (_canned_remediation(), RunUsage(input_tokens=100, output_tokens=30), [])
    monkeypatch.setattr(orch_mod, "run_diagnosis", AsyncMock(return_value=diag_rv))
    monkeypatch.setattr(
        orch_mod,
        "capture_health_snapshot",
        AsyncMock(return_value=_canned_baseline()),
    )
    monkeypatch.setattr(orch_mod, "run_remediation", AsyncMock(return_value=rem_rv))
    degraded_snap = _degraded_snapshot()
    degraded_rv = WatchdogResult(degraded=True, snapshot=degraded_snap)
    monkeypatch.setattr(orch_mod, "run_watchdog", AsyncMock(return_value=degraded_rv))

    async def _git_call(name, _args):
        if name == "revert_commit":
            raise RuntimeError("revert failed")
        return {"content": "ok"}

    mock_git_mcp.direct_call_tool = AsyncMock(side_effect=_git_call)

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )
    assert record.outcome == "rollback_failed"
    assert record.rollback_success is False


async def test_degraded_without_merge_skips_rollback(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    diag_rv = (_canned_report(), RunUsage(input_tokens=50, output_tokens=20), [])
    unmerged_rem = RemediationResult(
        success=False,
        actions_taken=["create_branch", "write_manifest", "commit_files"],
        tool_calls_count=3,
        mutation_attempted=True,
        merge_commit_sha=None,
        agent_branch="remediation/run-k8s-1",
        agent_commits=["abc1234"],
        gate_status="open",
    )
    rem_rv = (unmerged_rem, RunUsage(input_tokens=100, output_tokens=30), [])
    monkeypatch.setattr(orch_mod, "run_diagnosis", AsyncMock(return_value=diag_rv))
    monkeypatch.setattr(
        orch_mod,
        "capture_health_snapshot",
        AsyncMock(return_value=_canned_baseline()),
    )
    monkeypatch.setattr(orch_mod, "run_remediation", AsyncMock(return_value=rem_rv))
    degraded_snap = _degraded_snapshot()
    degraded_rv = WatchdogResult(degraded=True, snapshot=degraded_snap)
    monkeypatch.setattr(orch_mod, "run_watchdog", AsyncMock(return_value=degraded_rv))

    async def _git_call(name, _args):
        if name == "revert_commit":
            raise AssertionError("no revert")
        return {"content": "ok"}

    mock_git_mcp.direct_call_tool = AsyncMock(side_effect=_git_call)

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )
    assert record.outcome == "flux_degraded"
    assert record.rollback_triggered is False
    assert record.rollback_success is None


async def test_sequential_watchdog_k8s_path(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))

    rem_done_at: list[float] = []
    wtch_started_at: list[float] = []

    diag_rv = (_canned_report(), RunUsage(input_tokens=50, output_tokens=20), [])
    monkeypatch.setattr(orch_mod, "run_diagnosis", AsyncMock(return_value=diag_rv))
    monkeypatch.setattr(
        orch_mod,
        "capture_health_snapshot",
        AsyncMock(return_value=_canned_baseline()),
    )

    async def _rem_side_effect(*args, **kwargs):
        rem_done_at.append(time.monotonic())
        return (_canned_remediation(), RunUsage(input_tokens=100, output_tokens=30), [])

    async def _wtch_side_effect(*args, **kwargs):
        wtch_started_at.append(time.monotonic())
        return _watchdog_ok()

    monkeypatch.setattr(orch_mod, "run_remediation", _rem_side_effect)
    monkeypatch.setattr(orch_mod, "run_watchdog", _wtch_side_effect)

    await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )
    assert len(rem_done_at) == 1
    assert len(wtch_started_at) == 1
    assert wtch_started_at[0] > rem_done_at[0]


async def test_outcome_gate_failed(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    diag_rv = (_canned_report(), RunUsage(input_tokens=50, output_tokens=20), [])
    failed_rem = RemediationResult(
        success=False,
        actions_taken=[
            "create_branch",
            "write_manifest",
            "commit_files",
            "push_branch",
            "create_pr",
            "wait_for_gate",
        ],
        tool_calls_count=6,
        mutation_attempted=False,
        gate_status="closed",
    )
    rem_rv = (failed_rem, RunUsage(input_tokens=100, output_tokens=30), [])
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
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )
    assert record.outcome == "gate_failed"


async def test_gate_failed_unmerged_change_is_not_destructive(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    diag_rv = (_canned_report(), RunUsage(input_tokens=50, output_tokens=20), [])
    failed_rem = RemediationResult(
        success=False,
        actions_taken=["create_branch", "write_manifest", "commit_files", "create_pr"],
        tool_calls_count=4,
        mutation_attempted=True,
        merge_commit_sha=None,
        gate_status="closed",
    )
    rem_rv = (failed_rem, RunUsage(input_tokens=100, output_tokens=30), [])
    monkeypatch.setattr(orch_mod, "run_diagnosis", AsyncMock(return_value=diag_rv))
    monkeypatch.setattr(
        orch_mod,
        "capture_health_snapshot",
        AsyncMock(return_value=_canned_baseline()),
    )
    monkeypatch.setattr(orch_mod, "run_remediation", AsyncMock(return_value=rem_rv))
    monkeypatch.setattr(
        orch_mod,
        "run_watchdog",
        AsyncMock(
            return_value=WatchdogResult(degraded=True, snapshot=_canned_baseline())
        ),
    )

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )
    assert record.outcome == "gate_failed"
    assert record.destructive_repair is False


def test_outcome_budget_exhausted() -> None:
    pytest.skip("budget enforcement is prompt-level; see test_remediation.py")


def test_extract_tool_names_returns_names_in_order() -> None:
    from orchestrator.agent import _extract_tool_names
    from pydantic_ai.messages import ToolCallPart

    parts = [
        ToolCallPart(tool_name="create_branch", args={}),
        ToolCallPart(tool_name="commit_files", args={}),
    ]
    msg = SimpleNamespace(parts=parts)
    assert _extract_tool_names([msg]) == ["create_branch", "commit_files"]


def test_extract_tool_names_empty_msgs_returns_empty_list() -> None:
    from orchestrator.agent import _extract_tool_names

    assert _extract_tool_names([]) == []


def test_check_forbidden_actions_returns_violations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from orchestrator.agent import _check_forbidden_actions

    scenarios_root = tmp_path / "scenarios"
    scenarios_root.mkdir()
    (scenarios_root / "boundary-1").mkdir()
    (scenarios_root / "boundary-1" / "scenario.yaml").write_text(
        "forbidden_actions:\n  - nixos_rebuild\n"
    )
    monkeypatch.setenv("VIGIL_SCENARIOS_DIR", str(scenarios_root))
    result = _check_forbidden_actions("boundary-1", ["git_commit", "stage_generation"])
    assert result == ["stage_generation"]


def test_compute_destructive_repair_flags_forbidden_and_unreverted_harm() -> None:
    from orchestrator.agent import _compute_destructive_repair

    forbidden = _compute_destructive_repair(
        forbidden_violations=["nixos_rebuild"],
        mutation_applied=False,
        final_degraded=False,
        rollback_triggered=False,
        rollback_success=None,
    )
    assert forbidden is True

    mutate_degraded_no_rollback = _compute_destructive_repair(
        forbidden_violations=None,
        mutation_applied=True,
        final_degraded=True,
        rollback_triggered=False,
        rollback_success=None,
    )
    assert mutate_degraded_no_rollback is True

    rollback_failed = _compute_destructive_repair(
        forbidden_violations=None,
        mutation_applied=True,
        final_degraded=True,
        rollback_triggered=True,
        rollback_success=False,
    )
    assert rollback_failed is True


def test_compute_destructive_repair_clears_clean_and_reverted_runs() -> None:
    from orchestrator.agent import _compute_destructive_repair

    clean_success = _compute_destructive_repair(
        forbidden_violations=None,
        mutation_applied=True,
        final_degraded=False,
        rollback_triggered=False,
        rollback_success=None,
    )
    assert clean_success is False

    rollback_succeeded = _compute_destructive_repair(
        forbidden_violations=None,
        mutation_applied=True,
        final_degraded=True,
        rollback_triggered=True,
        rollback_success=True,
    )
    assert rollback_succeeded is False

    gate_blocked_unapplied = _compute_destructive_repair(
        forbidden_violations=None,
        mutation_applied=False,
        final_degraded=True,
        rollback_triggered=False,
        rollback_success=None,
    )
    assert gate_blocked_unapplied is False


def test_check_forbidden_actions_returns_empty_when_no_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from orchestrator.agent import _check_forbidden_actions

    scenarios_root = tmp_path / "scenarios"
    scenarios_root.mkdir()
    (scenarios_root / "boundary-1").mkdir()
    (scenarios_root / "boundary-1" / "scenario.yaml").write_text(
        "forbidden_actions:\n  - nixos_rebuild\n"
    )
    monkeypatch.setenv("VIGIL_SCENARIOS_DIR", str(scenarios_root))
    assert _check_forbidden_actions("boundary-1", ["git_commit"]) == []


def test_check_forbidden_actions_returns_empty_when_scenario_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from orchestrator.agent import _check_forbidden_actions

    scenarios_root = tmp_path / "scenarios"
    scenarios_root.mkdir()
    monkeypatch.setenv("VIGIL_SCENARIOS_DIR", str(scenarios_root))
    assert _check_forbidden_actions("does-not-exist", ["x"]) == []


def _make_scenario_dir(root: Path, scenario_id: str, forbidden: list[str]) -> None:
    d = root / scenario_id
    d.mkdir(parents=True, exist_ok=True)
    import yaml as _yaml

    (d / "scenario.yaml").write_text(_yaml.dump({"forbidden_actions": forbidden}))


def test_check_forbidden_actions_commit_files_maps_to_git_commit_k8s(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from orchestrator.agent import _check_forbidden_actions

    root = tmp_path / "scenarios"
    _make_scenario_dir(root, "k8s-1", ["git_commit_k8s"])
    monkeypatch.setenv("VIGIL_SCENARIOS_DIR", str(root))
    assert _check_forbidden_actions("k8s-1", ["commit_files"]) == ["commit_files"]


def test_check_forbidden_actions_create_pr_maps_to_git_commit_nix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from orchestrator.agent import _check_forbidden_actions

    root = tmp_path / "scenarios"
    _make_scenario_dir(root, "os-1", ["git_commit_nix"])
    monkeypatch.setenv("VIGIL_SCENARIOS_DIR", str(root))
    assert _check_forbidden_actions("os-1", ["create_pr"]) == ["create_pr"]


def test_check_forbidden_actions_write_manifest_maps_to_git_commit_k8s_and_nix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from orchestrator.agent import _check_forbidden_actions

    root = tmp_path / "scenarios"
    _make_scenario_dir(root, "sc", ["git_commit_k8s", "git_commit_nix"])
    monkeypatch.setenv("VIGIL_SCENARIOS_DIR", str(root))
    assert _check_forbidden_actions("sc", ["write_manifest"]) == ["write_manifest"]


def test_check_forbidden_actions_stage_generation_maps_to_nixos_rebuild(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from orchestrator.agent import _check_forbidden_actions

    root = tmp_path / "scenarios"
    _make_scenario_dir(root, "sc", ["nixos_rebuild"])
    monkeypatch.setenv("VIGIL_SCENARIOS_DIR", str(root))
    result = _check_forbidden_actions("sc", ["stage_generation"])
    assert result == ["stage_generation"]


def test_check_forbidden_actions_commit_generation_maps_to_nixos_rebuild(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from orchestrator.agent import _check_forbidden_actions

    root = tmp_path / "scenarios"
    _make_scenario_dir(root, "sc", ["nixos_rebuild"])
    monkeypatch.setenv("VIGIL_SCENARIOS_DIR", str(root))
    result = _check_forbidden_actions("sc", ["commit_generation"])
    assert result == ["commit_generation"]


def test_check_forbidden_actions_reconcile_kustomization_maps_to_flux_reconcile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from orchestrator.agent import _check_forbidden_actions

    root = tmp_path / "scenarios"
    _make_scenario_dir(root, "sc", ["flux_reconcile"])
    monkeypatch.setenv("VIGIL_SCENARIOS_DIR", str(root))
    result = _check_forbidden_actions("sc", ["reconcile_kustomization"])
    assert result == ["reconcile_kustomization"]


def test_check_forbidden_actions_unknown_tool_not_in_violations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from orchestrator.agent import _check_forbidden_actions

    root = tmp_path / "scenarios"
    _make_scenario_dir(root, "sc", ["git_commit_k8s"])
    monkeypatch.setenv("VIGIL_SCENARIOS_DIR", str(root))
    assert _check_forbidden_actions("sc", ["get_pods"]) == []


def test_check_forbidden_actions_empty_actions_returns_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from orchestrator.agent import _check_forbidden_actions

    root = tmp_path / "scenarios"
    _make_scenario_dir(root, "sc", ["git_commit_k8s"])
    monkeypatch.setenv("VIGIL_SCENARIOS_DIR", str(root))
    assert _check_forbidden_actions("sc", []) == []


def test_check_forbidden_actions_trigger_reconcile_maps_to_git_commit_nix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from orchestrator.agent import _check_forbidden_actions

    root = tmp_path / "scenarios"
    _make_scenario_dir(root, "os-1", ["git_commit_nix"])
    monkeypatch.setenv("VIGIL_SCENARIOS_DIR", str(root))
    assert _check_forbidden_actions("os-1", ["trigger_reconcile"]) == [
        "trigger_reconcile"
    ]


def test_check_forbidden_actions_trigger_reconcile_not_flagged_for_nixos_rebuild(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from orchestrator.agent import _check_forbidden_actions

    root = tmp_path / "scenarios"
    _make_scenario_dir(root, "os-1", ["nixos_rebuild"])
    monkeypatch.setenv("VIGIL_SCENARIOS_DIR", str(root))
    assert _check_forbidden_actions("os-1", ["trigger_reconcile"]) == []


def test_blocked_tool_names_includes_trigger_reconcile_for_git_commit_nix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from orchestrator.agent import _blocked_tool_names

    root = tmp_path / "scenarios"
    _make_scenario_dir(root, "os-1", ["git_commit_nix"])
    monkeypatch.setenv("VIGIL_SCENARIOS_DIR", str(root))
    assert "trigger_reconcile" in _blocked_tool_names("os-1")


def test_blocked_tool_names_excludes_trigger_reconcile_for_nixos_rebuild(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from orchestrator.agent import _blocked_tool_names

    root = tmp_path / "scenarios"
    _make_scenario_dir(root, "os-1", ["nixos_rebuild"])
    monkeypatch.setenv("VIGIL_SCENARIOS_DIR", str(root))
    blocked = _blocked_tool_names("os-1")
    assert "trigger_reconcile" not in blocked
    assert "stage_generation" in blocked
    assert "commit_generation" in blocked


async def test_no_rollback_when_watchdog_clears_within_settle_window(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    diag_rv = (_canned_report(), RunUsage(input_tokens=50, output_tokens=20), [])
    rem_rv = (_canned_remediation(), RunUsage(input_tokens=100, output_tokens=30), [])
    monkeypatch.setattr(orch_mod, "run_diagnosis", AsyncMock(return_value=diag_rv))
    monkeypatch.setattr(
        orch_mod,
        "capture_health_snapshot",
        AsyncMock(return_value=_canned_baseline()),
    )
    monkeypatch.setattr(orch_mod, "run_remediation", AsyncMock(return_value=rem_rv))
    degraded_snap = _degraded_snapshot()
    degraded_rv = WatchdogResult(degraded=True, snapshot=degraded_snap)
    monkeypatch.setattr(
        orch_mod,
        "run_watchdog",
        AsyncMock(side_effect=[degraded_rv, _watchdog_ok()]),
    )

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )
    assert record.outcome == "success"
    assert record.rollback_triggered is False


async def test_rollback_when_watchdog_stays_degraded(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    diag_rv = (_canned_report(), RunUsage(input_tokens=50, output_tokens=20), [])
    rem_rv = (_canned_remediation(), RunUsage(input_tokens=100, output_tokens=30), [])
    monkeypatch.setattr(orch_mod, "run_diagnosis", AsyncMock(return_value=diag_rv))
    monkeypatch.setattr(
        orch_mod,
        "capture_health_snapshot",
        AsyncMock(return_value=_canned_baseline()),
    )
    monkeypatch.setattr(orch_mod, "run_remediation", AsyncMock(return_value=rem_rv))
    degraded_snap = _degraded_snapshot()
    degraded_rv = WatchdogResult(
        degraded=True, snapshot=degraded_snap, reason="deadline_reached"
    )
    monkeypatch.setattr(orch_mod, "run_watchdog", AsyncMock(return_value=degraded_rv))
    mock_git_mcp.direct_call_tool = AsyncMock(
        return_value={"content": "reverted: cafebabe"}
    )
    mock_flux_mcp.direct_call_tool = AsyncMock(
        side_effect=lambda tool, args: (
            {"content": '{"found": true, "ready": true}'}
            if tool == "get_kustomization_status"
            else {"content": "reconciled"}
        )
    )

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )
    assert record.rollback_triggered is True
    assert record.outcome in ("rollback_succeeded", "rollback_failed")


def test_check_forbidden_actions_returns_tool_name_not_action_class(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from orchestrator.agent import _check_forbidden_actions

    root = tmp_path / "scenarios"
    _make_scenario_dir(root, "k8s-1", ["git_commit_k8s"])
    monkeypatch.setenv("VIGIL_SCENARIOS_DIR", str(root))
    violations = _check_forbidden_actions("k8s-1", ["commit_files"])
    assert violations == ["commit_files"]
    assert "git_commit_k8s" not in violations


def test_run_record_forbidden_action_violations_serialises_list() -> None:
    record = _make_run_record(forbidden_action_violations=["stage_generation"])
    data = json.loads(record.model_dump_json())
    assert data["forbidden_action_violations"] == ["stage_generation"]


def test_run_record_forbidden_action_violations_defaults_to_empty_list() -> None:
    record = _make_run_record()
    assert record.forbidden_action_violations == []


async def test_run_record_forbidden_action_violations_populated_on_success_path(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pydantic_ai.messages import ModelResponse, ToolCallPart

    scenarios_root = tmp_path / "scenarios"
    (scenarios_root / "boundary-1").mkdir(parents=True)
    (scenarios_root / "boundary-1" / "scenario.yaml").write_text(
        "forbidden_actions:\n  - nixos_rebuild\n"
    )
    monkeypatch.setenv("VIGIL_SCENARIOS_DIR", str(scenarios_root))
    _run_orch_setup(monkeypatch, tmp_path)
    violation_msg = ModelResponse(
        parts=[ToolCallPart(tool_name="stage_generation", args={})]
    )
    rem_rv = (
        _canned_remediation(),
        RunUsage(input_tokens=200, output_tokens=80),
        [violation_msg],
    )
    monkeypatch.setattr(orch_mod, "run_remediation", AsyncMock(return_value=rem_rv))
    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
        scenario="boundary-1",
    )
    assert record.forbidden_action_violations == ["stage_generation"]
    assert record.outcome == "success"


def test_run_record_accepts_baseline_degraded_outcome() -> None:
    record = _make_run_record(
        outcome="baseline_degraded", setup_error="cluster_apps_not_ready"
    )
    assert record.outcome == "baseline_degraded"


async def test_escalate_action_returns_escalated_record(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    escalate_report = _canned_report_with_action("escalate")
    diag_rv = (escalate_report, RunUsage(input_tokens=100, output_tokens=50), [])
    fetch_snapshot_mock = AsyncMock(return_value=_canned_baseline())
    run_remediation_mock = AsyncMock(
        return_value=(_canned_remediation(), RunUsage(), [])
    )
    run_watchdog_mock = AsyncMock(return_value=_watchdog_ok())
    monkeypatch.setattr(orch_mod, "run_diagnosis", AsyncMock(return_value=diag_rv))
    monkeypatch.setattr(orch_mod, "capture_health_snapshot", fetch_snapshot_mock)
    monkeypatch.setattr(orch_mod, "run_remediation", run_remediation_mock)
    monkeypatch.setattr(orch_mod, "run_watchdog", run_watchdog_mock)

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )

    assert record.outcome == "escalated"
    assert record.success_rate is None
    run_remediation_mock.assert_not_called()
    run_watchdog_mock.assert_not_called()


async def test_flux_reconcile_action_skips_precheck(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    flux_report = _canned_report_with_action("flux_reconcile")
    diag_rv = (flux_report, RunUsage(input_tokens=100, output_tokens=50), [])
    rem_rv = (_canned_remediation(), RunUsage(input_tokens=200, output_tokens=80), [])
    monkeypatch.setattr(orch_mod, "run_diagnosis", AsyncMock(return_value=diag_rv))
    monkeypatch.setattr(
        orch_mod, "capture_health_snapshot", AsyncMock(return_value=_canned_baseline())
    )
    run_remediation_mock = AsyncMock(return_value=rem_rv)
    monkeypatch.setattr(orch_mod, "run_remediation", run_remediation_mock)
    monkeypatch.setattr(
        orch_mod, "run_watchdog", AsyncMock(return_value=_watchdog_ok())
    )

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )

    assert record.outcome == "success"
    run_remediation_mock.assert_called_once()
    precheck_calls = [
        c
        for c in mock_flux_mcp.direct_call_tool.call_args_list
        if c.args and c.args[0] == "get_kustomization_status"
    ]
    assert len(precheck_calls) == 0


async def test_nixos_rebuild_action_routes_to_remediation(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    nixos_report = _canned_report_with_action("nixos_rebuild", target_host="hetzner-1")
    diag_rv = (nixos_report, RunUsage(input_tokens=100, output_tokens=50), [])
    rem_rv = (_canned_remediation(), RunUsage(input_tokens=200, output_tokens=80), [])
    run_remediation_mock = AsyncMock(return_value=rem_rv)
    run_watchdog_mock = AsyncMock(return_value=_watchdog_ok())
    monkeypatch.setattr(orch_mod, "run_diagnosis", AsyncMock(return_value=diag_rv))
    monkeypatch.setattr(
        orch_mod, "capture_health_snapshot", AsyncMock(return_value=_canned_baseline())
    )
    monkeypatch.setattr(orch_mod, "run_remediation", run_remediation_mock)
    monkeypatch.setattr(orch_mod, "run_watchdog", run_watchdog_mock)
    mock_nixos_mcp.direct_call_tool = AsyncMock(return_value={"content": "committed"})

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )

    assert record.outcome == "success"
    precheck_calls = [
        c
        for c in mock_flux_mcp.direct_call_tool.call_args_list
        if c.args and c.args[0] == "get_kustomization_status"
    ]
    assert len(precheck_calls) == 0
    run_remediation_mock.assert_called_once()
    run_watchdog_mock.assert_called_once()
    commit_calls = [
        c
        for c in mock_nixos_mcp.direct_call_tool.call_args_list
        if c.args and c.args[0] == "commit_generation"
    ]
    assert len(commit_calls) == 1
    assert commit_calls[0].args[1] == {"host": "hetzner-1"}


async def test_os_report_yields_watchdog_deps_with_nixos_target(
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    os_event = FaultEvent(
        receiver="vigil-webhook",
        status="firing",
        alerts=[
            {
                "status": "firing",
                "labels": {
                    "alertname": "NodeSystemdUnitFailed",
                    "node": "worker-1",
                    "systemd_unit": "nginx.service",
                },
                "annotations": {"summary": "unit down"},
                "startsAt": "2026-04-18T10:00:00Z",
                "endsAt": "0001-01-01T00:00:00Z",
            }
        ],
        groupLabels={"alertname": "NodeSystemdUnitFailed"},
        commonLabels={"node": "worker-1"},
        commonAnnotations={"summary": "unit down"},
        externalURL="http://alertmanager.monitoring:9093",
        version="4",
        groupKey='{}:{alertname="NodeSystemdUnitFailed"}',
    )
    nixos_report = _canned_report_with_action("nixos_rebuild", target_host="worker-1")
    diag_rv = (nixos_report, RunUsage(input_tokens=100, output_tokens=50), [])
    rem_rv = (_canned_remediation(), RunUsage(input_tokens=200, output_tokens=80), [])
    monkeypatch.setattr(orch_mod, "run_diagnosis", AsyncMock(return_value=diag_rv))
    monkeypatch.setattr(
        orch_mod, "capture_health_snapshot", AsyncMock(return_value=_canned_baseline())
    )
    monkeypatch.setattr(orch_mod, "run_remediation", AsyncMock(return_value=rem_rv))
    captured: list = []

    async def _capture_watchdog(deps):
        captured.append(deps)
        return _watchdog_ok()

    monkeypatch.setattr(orch_mod, "run_watchdog", _capture_watchdog)
    mock_nixos_mcp.direct_call_tool = AsyncMock(return_value={"content": "committed"})

    await run_orchestration(
        os_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
        scenario="os-1",
    )

    assert len(captured) == 1
    deps = captured[0]
    assert deps.nixos_mcp is mock_nixos_mcp
    assert deps.target_host == "worker-1"
    assert deps.os_check_kind == "systemd"
    assert deps.os_check_key == "nginx.service"
    assert deps.target_kind is None


async def test_nixos_rebuild_success_commit_generation_failure_surfaced(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    nixos_report = _canned_report_with_action("nixos_rebuild", target_host="hetzner-1")
    diag_rv = (nixos_report, RunUsage(input_tokens=100, output_tokens=50), [])
    rem_rv = (_canned_remediation(), RunUsage(input_tokens=200, output_tokens=80), [])
    monkeypatch.setattr(orch_mod, "run_diagnosis", AsyncMock(return_value=diag_rv))
    monkeypatch.setattr(
        orch_mod, "capture_health_snapshot", AsyncMock(return_value=_canned_baseline())
    )
    monkeypatch.setattr(orch_mod, "run_remediation", AsyncMock(return_value=rem_rv))
    monkeypatch.setattr(
        orch_mod, "run_watchdog", AsyncMock(return_value=_watchdog_ok())
    )
    mock_nixos_mcp.direct_call_tool = AsyncMock(
        side_effect=RuntimeError("commit refused")
    )

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )

    assert record.outcome == "commit_generation_failed"
    assert record.success_rate is False


async def test_k8s_success_does_not_commit_generation(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    diag_rv = (_canned_report(), RunUsage(input_tokens=100, output_tokens=50), [])
    rem_rv = (_canned_remediation(), RunUsage(input_tokens=200, output_tokens=80), [])
    monkeypatch.setattr(orch_mod, "run_diagnosis", AsyncMock(return_value=diag_rv))
    monkeypatch.setattr(
        orch_mod, "capture_health_snapshot", AsyncMock(return_value=_canned_baseline())
    )
    monkeypatch.setattr(orch_mod, "run_remediation", AsyncMock(return_value=rem_rv))
    monkeypatch.setattr(
        orch_mod, "run_watchdog", AsyncMock(return_value=_watchdog_ok())
    )
    mock_nixos_mcp.direct_call_tool = AsyncMock(return_value={"content": "x"})

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )

    assert record.outcome == "success"
    commit_calls = [
        c
        for c in mock_nixos_mcp.direct_call_tool.call_args_list
        if c.args and c.args[0] == "commit_generation"
    ]
    assert commit_calls == []


async def test_git_commit_nix_action_routes_to_remediation(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    nix_report = _canned_report_with_action("git_commit_nix", target_host="hetzner-1")
    diag_rv = (nix_report, RunUsage(input_tokens=100, output_tokens=50), [])
    rem_rv = (_canned_remediation(), RunUsage(input_tokens=200, output_tokens=80), [])
    run_remediation_mock = AsyncMock(return_value=rem_rv)
    monkeypatch.setattr(orch_mod, "run_diagnosis", AsyncMock(return_value=diag_rv))
    monkeypatch.setattr(
        orch_mod, "capture_health_snapshot", AsyncMock(return_value=_canned_baseline())
    )
    monkeypatch.setattr(orch_mod, "run_remediation", run_remediation_mock)
    monkeypatch.setattr(
        orch_mod, "run_watchdog", AsyncMock(return_value=_watchdog_ok())
    )

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )

    assert record.outcome == "success"
    precheck_calls = [
        c
        for c in mock_flux_mcp.direct_call_tool.call_args_list
        if c.args and c.args[0] == "get_kustomization_status"
    ]
    assert len(precheck_calls) == 0
    run_remediation_mock.assert_called_once()


def test_score_accuracy_flux_reconcile_matches_expected_action(
    tmp_path: Path,
) -> None:
    scenario_dir = tmp_path / "k8s-score"
    scenario_dir.mkdir(parents=True)
    (scenario_dir / "scenario.yaml").write_text("expected_action: flux_reconcile\n")

    import os as _os

    orig = _os.environ.get("VIGIL_SCENARIOS_DIR")
    _os.environ["VIGIL_SCENARIOS_DIR"] = str(tmp_path)
    try:
        result_match = _score_diagnosis_accuracy(
            "k8s-score", SimpleNamespace(recommended_action="flux_reconcile")
        )
        result_miss = _score_diagnosis_accuracy(
            "k8s-score", SimpleNamespace(recommended_action="nixos_rebuild")
        )
    finally:
        if orig is None:
            _os.environ.pop("VIGIL_SCENARIOS_DIR", None)
        else:
            _os.environ["VIGIL_SCENARIOS_DIR"] = orig

    assert result_match is True
    assert result_miss is False


def test_score_accuracy_none_when_expected_action_absent(
    tmp_path: Path,
) -> None:
    scenario_dir = tmp_path / "no-action"
    scenario_dir.mkdir(parents=True)
    (scenario_dir / "scenario.yaml").write_text("id: no-action\nname: x\n")

    import os as _os

    orig = _os.environ.get("VIGIL_SCENARIOS_DIR")
    _os.environ["VIGIL_SCENARIOS_DIR"] = str(tmp_path)
    try:
        result = _score_diagnosis_accuracy(
            "no-action", SimpleNamespace(recommended_action="flux_reconcile")
        )
    finally:
        if orig is None:
            _os.environ.pop("VIGIL_SCENARIOS_DIR", None)
        else:
            _os.environ["VIGIL_SCENARIOS_DIR"] = orig

    assert result is None


async def test_rollback_flux_reconcile_calls_reconcile_only() -> None:
    git_mcp = AsyncMock()
    git_mcp.direct_call_tool = AsyncMock(return_value={"content": "ok"})
    flux_mcp = AsyncMock()
    flux_mcp.direct_call_tool = AsyncMock(return_value={"content": "reconciled"})
    nixos_mcp = AsyncMock()
    nixos_mcp.direct_call_tool = AsyncMock(return_value={"content": "ok"})

    result = await _issue_rollback(
        "flux_reconcile", git_mcp, flux_mcp, nixos_mcp, None, None
    )

    assert result is True
    reconcile_calls = [
        c
        for c in flux_mcp.direct_call_tool.call_args_list
        if c.args and c.args[0] == "reconcile_kustomization"
    ]
    assert len(reconcile_calls) == 1
    assert reconcile_calls[0].args[1] == {
        "namespace": "flux-system",
        "name": "cluster-apps",
    }
    git_mcp.direct_call_tool.assert_not_called()
    nixos_mcp.direct_call_tool.assert_not_called()


async def test_rollback_nixos_rebuild_issues_no_durable_call() -> None:
    git_mcp = AsyncMock()
    git_mcp.direct_call_tool = AsyncMock(return_value={"content": "ok"})
    flux_mcp = AsyncMock()
    flux_mcp.direct_call_tool = AsyncMock(return_value={"content": "ok"})
    nixos_mcp = AsyncMock()
    nixos_mcp.direct_call_tool = AsyncMock(return_value={"content": "ok"})

    result = await _issue_rollback(
        "nixos_rebuild", git_mcp, flux_mcp, nixos_mcp, None, "hetzner-1"
    )

    assert result is True
    git_mcp.direct_call_tool.assert_not_called()
    flux_mcp.direct_call_tool.assert_not_called()
    nixos_mcp.direct_call_tool.assert_not_called()


async def test_rollback_git_commit_nix_calls_revert_and_trigger() -> None:
    git_mcp = AsyncMock()
    git_mcp.direct_call_tool = AsyncMock(return_value={"content": "reverted"})
    flux_mcp = AsyncMock()
    flux_mcp.direct_call_tool = AsyncMock(return_value={"content": "ok"})
    nixos_mcp = AsyncMock()
    nixos_mcp.direct_call_tool = AsyncMock(return_value={"content": "triggered"})

    result = await _issue_rollback(
        "git_commit_nix", git_mcp, flux_mcp, nixos_mcp, "abc123", "hetzner-1"
    )

    assert result is True
    revert_calls = [
        c
        for c in git_mcp.direct_call_tool.call_args_list
        if c.args and c.args[0] == "revert_commit"
    ]
    assert len(revert_calls) == 1
    assert revert_calls[0].args[1] == {"merge_commit_sha": "abc123"}
    trigger_calls = [
        c
        for c in nixos_mcp.direct_call_tool.call_args_list
        if c.args and c.args[0] == "trigger_reconcile"
    ]
    assert len(trigger_calls) == 1
    assert trigger_calls[0].args[1] == {"host": "hetzner-1"}
    flux_mcp.direct_call_tool.assert_not_called()


async def test_orchestrator_skips_diagnosis_when_context_unresolvable(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from diagnosis.context import ManifestPathUnresolvable

    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setattr(
        orch_mod,
        "capture_health_snapshot",
        AsyncMock(return_value=_canned_baseline()),
    )
    run_diagnosis_mock = AsyncMock(return_value=(_canned_report(), RunUsage(), []))
    monkeypatch.setattr(orch_mod, "run_diagnosis", run_diagnosis_mock)
    monkeypatch.setattr(
        orch_mod,
        "build_diagnosis_context",
        AsyncMock(side_effect=ManifestPathUnresolvable("no flux annotations")),
    )

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )

    assert record.outcome == "escalated"
    run_diagnosis_mock.assert_not_called()


async def test_orchestrator_classifies_diagnosis_context_model_retry(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pydantic_ai.exceptions import ModelRetry

    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setattr(
        orch_mod,
        "capture_health_snapshot",
        AsyncMock(return_value=_canned_baseline()),
    )
    run_diagnosis_mock = AsyncMock(return_value=(_canned_report(), RunUsage(), []))
    monkeypatch.setattr(orch_mod, "run_diagnosis", run_diagnosis_mock)
    monkeypatch.setattr(
        orch_mod,
        "build_diagnosis_context",
        AsyncMock(side_effect=ModelRetry("get_nix_path returned isError")),
    )

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )

    assert record.outcome == "abort"
    assert record.setup_error is not None
    assert record.setup_error.startswith("diagnosis_context_failed:")
    run_diagnosis_mock.assert_not_called()


async def test_orchestrator_escalates_on_resource_kind_unresolvable(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from diagnosis.context import ResourceKindUnresolvable

    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setattr(
        orch_mod,
        "capture_health_snapshot",
        AsyncMock(return_value=_canned_baseline()),
    )
    run_diagnosis_mock = AsyncMock(return_value=(_canned_report(), RunUsage(), []))
    monkeypatch.setattr(orch_mod, "run_diagnosis", run_diagnosis_mock)
    monkeypatch.setattr(
        orch_mod,
        "build_diagnosis_context",
        AsyncMock(side_effect=ResourceKindUnresolvable("no recognised label")),
    )

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )

    assert record.outcome == "escalated"
    assert record.setup_error == "no recognised label"
    run_diagnosis_mock.assert_not_called()


async def test_orchestrator_passes_base_branch_to_create_branch(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from diagnosis.context import DiagnosisContext

    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))

    ctx = DiagnosisContext(
        source_branch="eval-baseline",
        manifest_path="apps/vigil-app.yaml",
        live_yaml="live: yaml",
        declared_yaml="declared: yaml",
        diff="- live: yaml\n+ declared: yaml",
    )
    monkeypatch.setattr(
        orch_mod, "build_diagnosis_context", AsyncMock(return_value=ctx)
    )
    diag_rv = (_canned_report(), RunUsage(input_tokens=100, output_tokens=50), [])
    monkeypatch.setattr(orch_mod, "run_diagnosis", AsyncMock(return_value=diag_rv))
    monkeypatch.setattr(
        orch_mod, "capture_health_snapshot", AsyncMock(return_value=_canned_baseline())
    )
    monkeypatch.setattr(
        orch_mod,
        "run_remediation",
        AsyncMock(return_value=(_canned_remediation(), RunUsage(), [])),
    )
    monkeypatch.setattr(
        orch_mod, "run_watchdog", AsyncMock(return_value=_watchdog_ok())
    )

    await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )

    create_branch_calls = [
        c
        for c in mock_git_mcp.direct_call_tool.call_args_list
        if c.args and c.args[0] == "create_branch"
    ]
    assert len(create_branch_calls) >= 1
    args_dict = create_branch_calls[0].args[1]
    assert args_dict.get("base_branch") == "eval-baseline"

    run_remediation_mock = orch_mod.run_remediation
    assert run_remediation_mock.called
    _, kwargs = run_remediation_mock.call_args
    assert kwargs.get("source_branch") == "eval-baseline"


async def test_orchestrator_base_branch_falls_back_to_main_when_source_branch_empty(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from diagnosis.context import DiagnosisContext

    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))

    ctx = DiagnosisContext(
        source_branch="",
        manifest_path="apps/vigil-app.yaml",
        live_yaml="live: yaml",
        declared_yaml="declared: yaml",
        diff="",
    )
    monkeypatch.setattr(
        orch_mod, "build_diagnosis_context", AsyncMock(return_value=ctx)
    )
    diag_rv = (_canned_report(), RunUsage(input_tokens=100, output_tokens=50), [])
    monkeypatch.setattr(orch_mod, "run_diagnosis", AsyncMock(return_value=diag_rv))
    monkeypatch.setattr(
        orch_mod, "capture_health_snapshot", AsyncMock(return_value=_canned_baseline())
    )
    monkeypatch.setattr(
        orch_mod,
        "run_remediation",
        AsyncMock(return_value=(_canned_remediation(), RunUsage(), [])),
    )
    monkeypatch.setattr(
        orch_mod, "run_watchdog", AsyncMock(return_value=_watchdog_ok())
    )

    await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )

    create_branch_calls = [
        c
        for c in mock_git_mcp.direct_call_tool.call_args_list
        if c.args and c.args[0] == "create_branch"
    ]
    assert len(create_branch_calls) >= 1
    args_dict = create_branch_calls[0].args[1]
    assert args_dict.get("base_branch") == "main"


async def test_success_rate_false_when_forbidden_action_taken(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenarios_root = tmp_path / "scenarios"
    _make_scenario_dir(scenarios_root, "k8s-1", ["git_commit_k8s"])
    monkeypatch.setenv("VIGIL_SCENARIOS_DIR", str(scenarios_root))
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setattr(
        orch_mod, "_extract_tool_names", lambda _msgs: ["commit_files", "create_pr"]
    )

    diag_rv = (_canned_report(), RunUsage(input_tokens=100, output_tokens=50), [])
    rem_rv = (_canned_remediation(), RunUsage(input_tokens=200, output_tokens=80), [])
    monkeypatch.setattr(orch_mod, "run_diagnosis", AsyncMock(return_value=diag_rv))
    monkeypatch.setattr(
        orch_mod, "capture_health_snapshot", AsyncMock(return_value=_canned_baseline())
    )
    monkeypatch.setattr(orch_mod, "run_remediation", AsyncMock(return_value=rem_rv))
    monkeypatch.setattr(
        orch_mod, "run_watchdog", AsyncMock(return_value=_watchdog_ok())
    )

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
        scenario="k8s-1",
    )

    assert record.outcome == "success"
    assert record.success_rate is False
    assert len(record.forbidden_action_violations) > 0


async def test_success_rate_true_when_no_forbidden_actions(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenarios_root = tmp_path / "scenarios"
    _make_scenario_dir(scenarios_root, "k8s-1", [])
    monkeypatch.setenv("VIGIL_SCENARIOS_DIR", str(scenarios_root))
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))

    diag_rv = (_canned_report(), RunUsage(input_tokens=100, output_tokens=50), [])
    rem_rv = (_canned_remediation(), RunUsage(input_tokens=200, output_tokens=80), [])
    monkeypatch.setattr(orch_mod, "run_diagnosis", AsyncMock(return_value=diag_rv))
    monkeypatch.setattr(
        orch_mod, "capture_health_snapshot", AsyncMock(return_value=_canned_baseline())
    )
    monkeypatch.setattr(orch_mod, "run_remediation", AsyncMock(return_value=rem_rv))
    monkeypatch.setattr(
        orch_mod, "run_watchdog", AsyncMock(return_value=_watchdog_ok())
    )

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
        scenario="k8s-1",
    )

    assert record.outcome == "success"
    assert record.success_rate is True
    assert record.forbidden_action_violations == []


async def test_retry_succeeds_on_second_attempt(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))

    diag_rv = (_canned_report(), RunUsage(input_tokens=50, output_tokens=20), [])
    rem_rv = (_canned_remediation(), RunUsage(input_tokens=100, output_tokens=30), [])
    run_diagnosis_mock = AsyncMock(return_value=diag_rv)
    monkeypatch.setattr(orch_mod, "run_diagnosis", run_diagnosis_mock)
    monkeypatch.setattr(
        orch_mod, "capture_health_snapshot", AsyncMock(return_value=_canned_baseline())
    )
    monkeypatch.setattr(orch_mod, "run_remediation", AsyncMock(return_value=rem_rv))

    degraded_snap = _degraded_snapshot()
    degraded_rv = WatchdogResult(
        degraded=True, snapshot=degraded_snap, reason="deadline_reached"
    )
    monkeypatch.setattr(
        orch_mod,
        "run_watchdog",
        AsyncMock(side_effect=[degraded_rv, _watchdog_ok()]),
    )
    mock_git_mcp.direct_call_tool = AsyncMock(return_value={"content": "ok"})

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )

    assert record.outcome == "success"
    assert record.attempts == 2
    assert record.rollback_triggered is False
    assert run_diagnosis_mock.call_count == 2
    _, second_kwargs = run_diagnosis_mock.call_args_list[1]
    hint = second_kwargs.get("retry_hint")
    assert hint is not None
    assert "git_commit_k8s" in hint


async def test_all_retries_exhausted_triggers_rollback_on_last_attempt(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))

    diag_rv = (_canned_report(), RunUsage(input_tokens=50, output_tokens=20), [])
    rem_rv = (_canned_remediation(), RunUsage(input_tokens=100, output_tokens=30), [])
    run_diagnosis_mock = AsyncMock(return_value=diag_rv)
    monkeypatch.setattr(orch_mod, "run_diagnosis", run_diagnosis_mock)
    monkeypatch.setattr(
        orch_mod, "capture_health_snapshot", AsyncMock(return_value=_canned_baseline())
    )
    monkeypatch.setattr(orch_mod, "run_remediation", AsyncMock(return_value=rem_rv))

    degraded_snap = _degraded_snapshot()
    degraded_rv = WatchdogResult(degraded=True, snapshot=degraded_snap)
    monkeypatch.setattr(orch_mod, "run_watchdog", AsyncMock(return_value=degraded_rv))
    mock_git_mcp.direct_call_tool = AsyncMock(
        return_value={"content": "reverted: cafebabe"}
    )
    mock_flux_mcp.direct_call_tool = AsyncMock(return_value={"content": "reconciled"})

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )

    assert record.attempts == 3
    assert record.rollback_triggered is True
    assert record.outcome in ("rollback_succeeded", "rollback_failed")
    assert run_diagnosis_mock.call_count == 3
    revert_calls = [
        c
        for c in mock_git_mcp.direct_call_tool.call_args_list
        if c.args and c.args[0] == "revert_commit"
    ]
    assert len(revert_calls) == 1


async def test_gate_failed_does_not_retry(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))

    diag_rv = (_canned_report(), RunUsage(input_tokens=50, output_tokens=20), [])
    failed_rem = RemediationResult(
        success=False,
        actions_taken=["create_branch", "write_manifest", "commit_files", "create_pr"],
        tool_calls_count=4,
        mutation_attempted=False,
        gate_status="closed",
    )
    rem_rv = (failed_rem, RunUsage(input_tokens=100, output_tokens=30), [])
    run_diagnosis_mock = AsyncMock(return_value=diag_rv)
    monkeypatch.setattr(orch_mod, "run_diagnosis", run_diagnosis_mock)
    monkeypatch.setattr(
        orch_mod, "capture_health_snapshot", AsyncMock(return_value=_canned_baseline())
    )
    monkeypatch.setattr(orch_mod, "run_remediation", AsyncMock(return_value=rem_rv))
    monkeypatch.setattr(
        orch_mod, "run_watchdog", AsyncMock(return_value=_watchdog_ok())
    )

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )

    assert record.outcome == "gate_failed"
    assert record.attempts == 1
    assert run_diagnosis_mock.call_count == 1


async def test_blocked_tool_refusal_does_not_retry(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))

    diag_rv = (_canned_report(), RunUsage(input_tokens=50, output_tokens=20), [])
    run_diagnosis_mock = AsyncMock(return_value=diag_rv)
    monkeypatch.setattr(orch_mod, "run_diagnosis", run_diagnosis_mock)
    monkeypatch.setattr(
        orch_mod, "capture_health_snapshot", AsyncMock(return_value=_canned_baseline())
    )
    refused_rem = RemediationResult(
        success=False,
        actions_taken=["refused_protected_branch"],
        tool_calls_count=0,
        mutation_attempted=False,
    )
    rem_mock = AsyncMock(
        return_value=(refused_rem, RunUsage(input_tokens=10, output_tokens=5), [])
    )
    monkeypatch.setattr(orch_mod, "run_remediation", rem_mock)
    degraded_rv = WatchdogResult(
        degraded=True, snapshot=_degraded_snapshot(), reason="deadline_reached"
    )
    monkeypatch.setattr(orch_mod, "run_watchdog", AsyncMock(return_value=degraded_rv))

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )

    assert record.outcome == "escalated"
    assert record.attempts == 1
    assert run_diagnosis_mock.call_count == 1
    assert rem_mock.call_count == 1


async def test_earlier_merge_preserved_when_retry_escalates(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))

    merge_report = _canned_report()
    escalate_report = _canned_report_with_action("escalate")
    merge_rv = (merge_report, RunUsage(input_tokens=50, output_tokens=20), [])
    escalate_rv = (escalate_report, RunUsage(input_tokens=30, output_tokens=10), [])
    run_diagnosis_mock = AsyncMock(side_effect=[merge_rv, escalate_rv])
    monkeypatch.setattr(orch_mod, "run_diagnosis", run_diagnosis_mock)
    monkeypatch.setattr(
        orch_mod, "capture_health_snapshot", AsyncMock(return_value=_canned_baseline())
    )
    rem_rv = (_canned_remediation(), RunUsage(input_tokens=100, output_tokens=30), [])
    monkeypatch.setattr(orch_mod, "run_remediation", AsyncMock(return_value=rem_rv))
    degraded_rv = WatchdogResult(
        degraded=True, snapshot=_degraded_snapshot(), reason="deadline_reached"
    )
    monkeypatch.setattr(orch_mod, "run_watchdog", AsyncMock(return_value=degraded_rv))
    mock_git_mcp.direct_call_tool = AsyncMock(return_value={"content": "ok"})
    mock_flux_mcp.direct_call_tool = AsyncMock(return_value={"content": "reconciled"})

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )

    assert run_diagnosis_mock.call_count == 2
    assert record.outcome != "escalated"
    assert record.agent_commits == ["deadbeef1234567"]
    assert record.agent_branch == "remediation/run-k8s-1"


async def test_earlier_merge_preserved_when_retry_gate_fails(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))

    diag_rv = (_canned_report(), RunUsage(input_tokens=50, output_tokens=20), [])
    run_diagnosis_mock = AsyncMock(return_value=diag_rv)
    monkeypatch.setattr(orch_mod, "run_diagnosis", run_diagnosis_mock)
    monkeypatch.setattr(
        orch_mod, "capture_health_snapshot", AsyncMock(return_value=_canned_baseline())
    )
    gate_failed_rem = RemediationResult(
        success=False,
        actions_taken=["create_branch", "write_manifest", "commit_files", "create_pr"],
        tool_calls_count=4,
        mutation_attempted=True,
        merge_commit_sha=None,
        agent_branch="remediation/run-attempt-2",
        agent_commits=["facefeed0000000"],
        gate_status="closed",
    )
    rem_mock = AsyncMock(
        side_effect=[
            (_canned_remediation(), RunUsage(input_tokens=100, output_tokens=30), []),
            (gate_failed_rem, RunUsage(input_tokens=80, output_tokens=20), []),
        ]
    )
    monkeypatch.setattr(orch_mod, "run_remediation", rem_mock)
    healthy_after_retry = WatchdogResult(
        degraded=True, snapshot=_degraded_snapshot(), reason="deadline_reached"
    )
    monkeypatch.setattr(
        orch_mod, "run_watchdog", AsyncMock(return_value=healthy_after_retry)
    )
    mock_git_mcp.direct_call_tool = AsyncMock(return_value={"content": "ok"})
    mock_flux_mcp.direct_call_tool = AsyncMock(return_value={"content": "reconciled"})

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )

    assert record.outcome != "gate_failed"
    assert record.agent_commits == ["deadbeef1234567"]
    assert record.agent_branch == "remediation/run-k8s-1"


async def test_late_escalate_after_merged_degraded_rolls_back(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))

    merge_report = _canned_report()
    escalate_report = _canned_report_with_action("escalate")
    merge_rv = (merge_report, RunUsage(input_tokens=50, output_tokens=20), [])
    escalate_rv = (escalate_report, RunUsage(input_tokens=30, output_tokens=10), [])
    run_diagnosis_mock = AsyncMock(side_effect=[merge_rv, merge_rv, escalate_rv])
    monkeypatch.setattr(orch_mod, "run_diagnosis", run_diagnosis_mock)
    monkeypatch.setattr(
        orch_mod, "capture_health_snapshot", AsyncMock(return_value=_canned_baseline())
    )
    rem_rv = (_canned_remediation(), RunUsage(input_tokens=100, output_tokens=30), [])
    monkeypatch.setattr(orch_mod, "run_remediation", AsyncMock(return_value=rem_rv))
    degraded_rv = WatchdogResult(
        degraded=True, snapshot=_degraded_snapshot(), reason="deadline_reached"
    )
    monkeypatch.setattr(orch_mod, "run_watchdog", AsyncMock(return_value=degraded_rv))
    mock_git_mcp.direct_call_tool = AsyncMock(
        return_value={"content": "reverted: cafebabe"}
    )
    mock_flux_mcp.direct_call_tool = AsyncMock(return_value={"content": "reconciled"})

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )

    assert run_diagnosis_mock.call_count == 3
    assert record.outcome == "rollback_succeeded"
    assert record.rollback_triggered is True
    assert record.rollback_success is True
    assert record.destructive_repair is False
    revert_calls = [
        c
        for c in mock_git_mcp.direct_call_tool.call_args_list
        if c.args and c.args[0] == "revert_commit"
    ]
    assert len(revert_calls) == 1


def _confidence_report(action: str, confidence: float) -> DiagnosisReport:
    is_git = action in {"git_commit_k8s", "git_commit_nix"}
    return DiagnosisReport(
        root_cause="confidence-gated fault",
        root_cause_component="vigil-app",
        severity="high",
        affected_resources=["default/vigil-app"],
        evidence="evidence",
        drift_classification=_ACTION_DRIFT[action],
        recommended_action=action,
        confidence=confidence,
        target_host=(
            "worker-1" if action in {"nixos_rebuild", "git_commit_nix"} else None
        ),
        manifest_path="apps/vigil-app.yaml" if is_git else None,
        patch_body="apiVersion: apps/v1\n" if is_git else None,
    )


def _gate_setup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    report: DiagnosisReport,
    remediation_result: RemediationResult,
) -> AsyncMock:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.delenv("GIT_SHA7", raising=False)
    diag_rv = (report, RunUsage(input_tokens=100, output_tokens=50), [])
    rem_rv = (remediation_result, RunUsage(input_tokens=200, output_tokens=80), [])
    monkeypatch.setattr(orch_mod, "run_diagnosis", AsyncMock(return_value=diag_rv))
    monkeypatch.setattr(
        orch_mod, "capture_health_snapshot", AsyncMock(return_value=_canned_baseline())
    )
    rem_mock = AsyncMock(return_value=rem_rv)
    monkeypatch.setattr(orch_mod, "run_remediation", rem_mock)
    monkeypatch.setattr(
        orch_mod, "run_watchdog", AsyncMock(return_value=_watchdog_ok())
    )
    return rem_mock


async def test_gate_high_confidence_takes_auto_path(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = _confidence_report("git_commit_k8s", 0.95)
    rem_mock = _gate_setup(monkeypatch, tmp_path, report, _canned_remediation())

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )

    assert record.outcome == "success"
    assert rem_mock.await_args.kwargs.get("require_human_review", False) is False


async def test_gate_review_confidence_git_action_awaits_human_review(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = _confidence_report("git_commit_k8s", 0.5)
    review_result = RemediationResult(
        success=True,
        actions_taken=["clone_repo", "create_pr"],
        tool_calls_count=2,
        mutation_attempted=True,
        agent_branch="remediation/run-x",
        agent_commits=["abc1234"],
        gate_status="awaiting_review",
    )
    rem_mock = _gate_setup(monkeypatch, tmp_path, report, review_result)

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )

    assert record.outcome == "awaiting_human_review"
    assert record.success_rate is False
    assert record.rollback_triggered is False
    assert record.rollback_success is None
    assert record.agent_branch == "remediation/run-x"
    assert record.agent_commits == ["abc1234"]
    assert record.gate_status == "awaiting_review"
    assert rem_mock.await_args.kwargs.get("require_human_review") is True


async def test_gate_review_captures_usage_on_remediation_retry_exhaustion(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = _confidence_report("git_commit_k8s", 0.5)
    _gate_setup(monkeypatch, tmp_path, report, _canned_remediation())
    monkeypatch.setattr(
        orch_mod,
        "run_remediation",
        AsyncMock(
            side_effect=RemediationOutputRetryExhausted(
                RunUsage(input_tokens=200, output_tokens=80),
                [],
                UnexpectedModelBehavior("exceeded max retries count of 3"),
            )
        ),
    )

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )

    assert record.outcome == "abort"
    assert record.setup_error is not None
    assert "retry_exhausted:remediation" in record.setup_error
    assert record.total_input_tokens == 300
    assert record.total_output_tokens == 130


async def test_gate_review_confidence_non_git_action_escalates(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = _confidence_report("nixos_rebuild", 0.5)
    rem_mock = _gate_setup(monkeypatch, tmp_path, report, _canned_remediation())

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )

    assert record.outcome == "escalated"
    rem_mock.assert_not_awaited()


async def test_gate_low_confidence_escalates(
    sample_fault_event: FaultEvent,
    mock_kubectl_mcp: AsyncMock,
    mock_flux_mcp: AsyncMock,
    mock_nixos_mcp: AsyncMock,
    mock_git_mcp: AsyncMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = _confidence_report("git_commit_k8s", 0.2)
    rem_mock = _gate_setup(monkeypatch, tmp_path, report, _canned_remediation())

    record = await run_orchestration(
        sample_fault_event,
        kubectl_mcp=mock_kubectl_mcp,
        flux_mcp=mock_flux_mcp,
        nixos_mcp=mock_nixos_mcp,
        git_mcp=mock_git_mcp,
    )

    assert record.outcome == "escalated"
    rem_mock.assert_not_awaited()
