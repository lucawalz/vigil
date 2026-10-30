"""Tests for the eval CLI setup-error stub records."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from eval.aggregate import _last_try_per_incident, _load_records
from eval.cli import _run_id_for, _write_setup_error_record
from orchestrator.agent import retry_run_id


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


_PER_TRY_WAIT_S = 10
_SCENARIO = "k8s-rollback-1"
_SEED = 1
_MODEL = "test-model"


def test_run_reports_a_harness_timeout_when_a_queued_try_never_finishes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from unittest.mock import MagicMock

    import eval.cli as cli_mod
    import eval.harness as harness_mod
    from click.testing import CliRunner

    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    run_id = _run_id_for(_SCENARIO, _SEED, _MODEL)
    first_try = runs_dir / f"{run_id}.json"
    monkeypatch.setenv("VIGIL_WEBHOOK_SECRET", "s")
    monkeypatch.setattr(harness_mod, "_build_fault_event", lambda *a, **k: {})

    def _response(body: dict) -> MagicMock:
        resp = MagicMock()
        resp.json = MagicMock(return_value=body)
        return resp

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, **kwargs):
            return _response({"run_timeout_s": _PER_TRY_WAIT_S})

        async def post(self, url, **kwargs):
            return _response({"run_id": run_id})

    monkeypatch.setattr(harness_mod.httpx, "AsyncClient", FakeClient)
    now = [0.0]

    class FakeLoop:
        def time(self) -> float:
            return now[0]

    index_path = tmp_path / "runs_index.jsonl"
    first_record = {
        "run_id": run_id,
        "scenario": _SCENARIO,
        "seed": _SEED,
        "model": _MODEL,
        "incident_id": run_id,
        "attempts": 1,
        "outcome": "rollback_succeeded",
        "success_rate": False,
        "rollback_triggered": True,
        "rollback_success": True,
        "retry_queued": True,
        "started_at": "2026-10-30T10:00:00Z",
        "ended_at": "2026-10-30T10:20:00Z",
    }

    async def fake_sleep(t):
        now[0] += t
        if not first_try.exists():
            first_try.write_text(json.dumps(first_record))
            with index_path.open("a") as fh:
                fh.write(json.dumps(first_record) + "\n")

    async def fake_run_one(**kwargs) -> Path:
        monkeypatch.setattr(harness_mod.asyncio, "get_event_loop", lambda: FakeLoop())
        monkeypatch.setattr(harness_mod.asyncio, "sleep", fake_sleep)
        return await harness_mod.trigger_and_wait(
            scenario_id=kwargs["scenario_id"],
            seed=kwargs["seed"],
            orchestrator_url=kwargs["orchestrator_url"],
            runs_dir=kwargs["runs_dir"],
            model=kwargs["model"],
            timeout_s=kwargs["timeout_s"],
        )

    monkeypatch.setattr(cli_mod, "run_one", fake_run_one)

    result = CliRunner().invoke(
        cli_mod.cli,
        [
            "run",
            "--scenario",
            _SCENARIO,
            "--seed",
            str(_SEED),
            "--model",
            _MODEL,
            "--timeout",
            str(_PER_TRY_WAIT_S),
            "--runs-dir",
            str(runs_dir),
        ],
    )

    assert result.exit_code != 0
    assert json.loads(first_try.read_text()) == first_record
    timeout_record = json.loads(
        (runs_dir / f"{retry_run_id(run_id, 2)}.json").read_text()
    )
    assert timeout_record["outcome"] == "harness_timeout"
    assert timeout_record["incident_id"] == run_id
    kept = _last_try_per_incident(_load_records(runs_dir, index_path))
    assert [r["outcome"] for r in kept] == ["harness_timeout"]


def test_write_setup_error_record_carries_the_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VIGIL_EVAL_TARGET", "runner")
    runs_dir = tmp_path / "runs"
    _write_setup_error_record("k8s-3g", 1, "m", runs_dir, "boom")
    record = json.loads(next(runs_dir.glob("*.json")).read_text())
    index = json.loads((tmp_path / "runs_index.jsonl").read_text().splitlines()[0])
    assert record["target"] == "runner"
    assert index["target"] == "runner"
