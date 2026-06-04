"""Tests for the eval CLI setup-error stub records."""

from __future__ import annotations

import json
from pathlib import Path

from eval.cli import _run_id_for, _write_setup_error_record


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


def test_write_setup_error_record_does_not_clobber_existing(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    run_id = _run_id_for("k8s-3g", 1, "deepseek-v3.2:cloud")
    real = runs_dir / f"{run_id}.json"
    real.write_text(json.dumps({"run_id": run_id, "outcome": "gate_failed"}))
    index_path = tmp_path / "runs_index.jsonl"

    wrote = _write_setup_error_record(
        "k8s-3g",
        1,
        "deepseek-v3.2:cloud",
        runs_dir,
        "No result file within 600s",
        outcome="harness_timeout",
    )

    assert wrote is False
    assert json.loads(real.read_text())["outcome"] == "gate_failed"
    assert not index_path.exists()


def test_write_setup_error_record_writes_when_absent(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"

    wrote = _write_setup_error_record(
        "k8s-3g", 1, "m", runs_dir, "boom", outcome="harness_timeout"
    )

    assert wrote is True
    files = list(runs_dir.glob("*.json"))
    assert len(files) == 1
    record = json.loads(files[0].read_text())
    assert record["outcome"] == "harness_timeout"
    assert record["setup_error"] == "boom"


def test_default_timeout_exceeds_orchestrator_run_cap() -> None:
    from eval.harness import _ORCHESTRATOR_RUN_TIMEOUT_S, DEFAULT_TIMEOUT_S

    assert DEFAULT_TIMEOUT_S > _ORCHESTRATOR_RUN_TIMEOUT_S
