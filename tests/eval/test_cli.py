"""Tests for the eval CLI setup-error stub records."""

from __future__ import annotations

import json
from pathlib import Path

from eval.cli import _write_setup_error_record


def test_write_setup_error_record_uses_setup_error_and_distinct_timestamps(
    tmp_path: Path,
) -> None:
    runs_dir = tmp_path / "runs"
    _write_setup_error_record(
        "k8s-4g",
        1,
        "deepseek-v3.2:cloud",
        runs_dir,
        "No result file for run_id=k8s-4g_1 within 600s",
        outcome="diagnosis_timeout",
        started_at="2026-06-04T01:00:00Z",
    )

    files = list(runs_dir.glob("*.json"))
    assert len(files) == 1
    record = json.loads(files[0].read_text())

    assert record["outcome"] == "diagnosis_timeout"
    assert record["setup_error"].startswith("No result file")
    assert "error_message" not in record
    assert record["started_at"] == "2026-06-04T01:00:00Z"
    assert record["started_at"] != record["ended_at"]
    assert record["forbidden_action_violations"] == []
