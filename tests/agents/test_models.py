"""Schema validation tests for agent Pydantic models."""

import pytest
from diagnosis.models import DiagnosisReport, ProposedPatch
from orchestrator.models import FaultEvent, RunRecord
from pydantic import ValidationError
from watchdog.models import HealthSnapshot, WatchdogResult


def test_fault_event_accepts_alertmanager_payload(
    sample_fault_event: FaultEvent,
) -> None:
    assert sample_fault_event.receiver == "vigil-webhook"
    assert sample_fault_event.alerts[0]["labels"]["deployment"] == "vigil-app"
    assert sample_fault_event.truncatedAlerts == 0


def test_diagnosis_report_rejects_bad_severity() -> None:
    with pytest.raises(ValidationError):
        DiagnosisReport(
            root_cause="image tag wrong",
            root_cause_component="vigil-app:bad-tag-v9",
            severity="catastrophic",
            affected_resources=["default/vigil-app"],
            evidence="Failed to pull image",
            recommended_action="git_commit",
            confidence=0.9,
            requires_os_level=False,
        )


def test_diagnosis_report_rejects_bad_action() -> None:
    with pytest.raises(ValidationError):
        DiagnosisReport(
            root_cause="image tag wrong",
            root_cause_component="vigil-app:bad-tag-v9",
            severity="high",
            affected_resources=["default/vigil-app"],
            evidence="Failed to pull image",
            recommended_action="delete_cluster",
            confidence=0.9,
            requires_os_level=False,
        )


def test_diagnosis_report_confidence_bounds() -> None:
    with pytest.raises(ValidationError):
        DiagnosisReport(
            root_cause="x",
            root_cause_component="y",
            severity="low",
            affected_resources=[],
            evidence="z",
            recommended_action="git_commit",
            confidence=1.5,  # out of range
            requires_os_level=False,
        )


def test_diagnosis_report_accepts_git_commit_action() -> None:
    r = DiagnosisReport(
        root_cause="image tag wrong",
        root_cause_component="vigil-app:bad-tag-v9",
        severity="high",
        affected_resources=["default/vigil-app"],
        evidence="Failed to pull image",
        recommended_action="git_commit",
        confidence=0.9,
        requires_os_level=False,
    )
    assert r.manifest_path is None
    assert r.proposed_patch is None


def test_diagnosis_report_backward_compat_no_new_fields() -> None:
    r = DiagnosisReport(
        root_cause="image tag wrong",
        root_cause_component="vigil-app:bad-tag-v9",
        severity="high",
        affected_resources=["default/vigil-app"],
        evidence="Failed to pull image",
        recommended_action="git_commit",
        confidence=0.9,
        requires_os_level=False,
    )
    assert r.manifest_path is None
    assert r.proposed_patch is None


def test_diagnosis_report_with_proposed_patch_roundtrip() -> None:
    patch = ProposedPatch(
        resource_kind="Deployment",
        resource_name="vigil-app",
        resource_namespace="default",
        patch_body="apiVersion: apps/v1\nkind: Deployment\n",
    )
    r = DiagnosisReport(
        root_cause="image tag wrong",
        root_cause_component="vigil-app:bad-tag-v9",
        severity="high",
        affected_resources=["default/vigil-app"],
        evidence="Failed to pull image",
        recommended_action="git_commit",
        confidence=0.9,
        requires_os_level=False,
        manifest_path="apps/vigil/deployment.yaml",
        proposed_patch=patch,
    )
    j = r.model_dump_json()
    assert DiagnosisReport.model_validate_json(j) == r


def test_proposed_patch_requires_all_four_fields() -> None:
    base = dict(
        resource_kind="Deployment",
        resource_name="vigil-app",
        resource_namespace="default",
        patch_body="apiVersion: apps/v1\nkind: Deployment\n",
    )
    for field in ("resource_kind", "resource_name", "resource_namespace", "patch_body"):
        kwargs = {k: v for k, v in base.items() if k != field}
        with pytest.raises(ValidationError):
            ProposedPatch(**kwargs)


def test_diagnosis_report_rejects_delete_cluster_still_invalid() -> None:
    with pytest.raises(ValidationError):
        DiagnosisReport(
            root_cause="image tag wrong",
            root_cause_component="vigil-app:bad-tag-v9",
            severity="high",
            affected_resources=["default/vigil-app"],
            evidence="Failed to pull image",
            recommended_action="delete_cluster",
            confidence=0.9,
            requires_os_level=False,
        )


def test_run_record_roundtrip() -> None:
    record = RunRecord(
        run_id="k8s-1_seed-20260418T100000Z_llama-3.3-70b_abcd123",
        scenario="k8s-1",
        seed="seed-20260418T100000Z",
        model="llama-3.3-70b",
        git_sha7="abcd123",
        started_at="2026-04-18T10:00:00Z",
        ended_at="2026-04-18T10:02:00Z",
        outcome="success",
        success_rate=True,
        diagnosis_accuracy=True,
        MTTR_s=90.5,
        destructive_repair=True,
        rollback_triggered=False,
        rollback_success=None,
        total_input_tokens=8500,
        total_output_tokens=900,
        total_tool_calls=7,
        iteration_count=6,
        autonomy_level="full",
        actions_taken=["apply_patch"],
        agent_branch="remediation/run-abc123",
        agent_commits=["sha1", "sha2"],
        gate_status="success",
    )
    j = record.model_dump_json()
    assert RunRecord.model_validate_json(j) == record


def test_run_record_new_fields_default_none() -> None:
    record = RunRecord(
        run_id="k8s-1_seed-20260418T100000Z_llama-3.3-70b_abcd123",
        scenario="k8s-1",
        seed="seed-20260418T100000Z",
        model="llama-3.3-70b",
        git_sha7="abcd123",
        started_at="2026-04-18T10:00:00Z",
        ended_at="2026-04-18T10:02:00Z",
        outcome="success",
        success_rate=True,
        diagnosis_accuracy=None,
        MTTR_s=None,
        destructive_repair=False,
        rollback_triggered=False,
        rollback_success=None,
        total_input_tokens=0,
        total_output_tokens=0,
        total_tool_calls=0,
        iteration_count=0,
        autonomy_level="full",
        actions_taken=[],
    )
    assert record.agent_branch is None
    assert record.agent_commits is None
    assert record.gate_status is None


def test_run_record_legacy_json_backward_compat() -> None:
    record = RunRecord(
        run_id="k8s-1_seed-20260418T100000Z_llama-3.3-70b_abcd123",
        scenario="k8s-1",
        seed="seed-20260418T100000Z",
        model="llama-3.3-70b",
        git_sha7="abcd123",
        started_at="2026-04-18T10:00:00Z",
        ended_at="2026-04-18T10:02:00Z",
        outcome="success",
        success_rate=True,
        diagnosis_accuracy=None,
        MTTR_s=None,
        destructive_repair=False,
        rollback_triggered=False,
        rollback_success=None,
        total_input_tokens=0,
        total_output_tokens=0,
        total_tool_calls=0,
        iteration_count=0,
        autonomy_level="full",
        actions_taken=[],
    )
    import json

    data = record.model_dump()
    for key in ("agent_branch", "agent_commits", "gate_status"):
        data.pop(key, None)
    legacy = RunRecord.model_validate_json(json.dumps(data))
    assert legacy.agent_branch is None


def test_watchdog_result_default_not_degraded() -> None:
    r = WatchdogResult(degraded=False)
    assert r.degraded is False
    assert r.snapshot is None


def test_health_snapshot_validates() -> None:
    s = HealthSnapshot(
        ready_pods=3,
        total_pods=3,
        endpoints_healthy=True,
        captured_at="2026-04-18T10:00:00Z",
    )
    assert s.ready_pods == 3
