"""Null-sentinel coercion on nullable model fields."""

from __future__ import annotations

import pytest
from diagnosis.models import DiagnosisReport
from pydantic import ValidationError
from remediation.models import RemediationResult

_VALID_REQUIRED = {
    "success": True,
    "actions_taken": ["apply_patch"],
    "tool_calls_count": 3,
    "mutation_attempted": True,
}


@pytest.mark.parametrize(
    ("field", "sentinel"),
    [
        ("agent_commits", "None"),
        ("merge_commit_sha", "null"),
        ("gate_status", ""),
        ("agent_branch", "nil"),
    ],
)
def test_remediation_result_coerces_sentinel_to_none(field: str, sentinel: str) -> None:
    result = RemediationResult(**_VALID_REQUIRED, **{field: sentinel})
    assert getattr(result, field) is None


def test_remediation_result_keeps_real_list_value() -> None:
    result = RemediationResult(**_VALID_REQUIRED, agent_commits=["abc123"])
    assert result.agent_commits == ["abc123"]


def test_remediation_result_rejects_sentinel_on_non_nullable_field() -> None:
    payload = {**_VALID_REQUIRED}
    payload["success"] = "none"
    with pytest.raises(ValidationError):
        RemediationResult(**payload)


def test_diagnosis_report_coerces_patch_body_sentinel() -> None:
    report = DiagnosisReport(
        root_cause="image tag wrong",
        root_cause_component="vigil-app:bad-tag-v9",
        severity="high",
        affected_resources=["default/vigil-app"],
        evidence="Failed to pull image",
        drift_classification="live_only_drift",
        recommended_action="flux_reconcile",
        confidence=0.9,
        patch_body="None",
    )
    assert report.patch_body is None
