"""Tests for aggregate.py: aggregate_runs, write_report, and aggregate CLI command."""

from __future__ import annotations

import json
import re
import statistics
from pathlib import Path

import pytest
from click.testing import CliRunner


def _write_run(
    runs_dir: Path,
    index_path: Path,
    *,
    run_id: str,
    scenario: str,
    seed: int,
    model: str,
    success: bool = True,
    mttr: float = 10.0,
    diagnosis_accuracy: bool | None = None,
) -> None:
    record = {
        "run_id": run_id,
        "scenario": scenario,
        "seed": str(seed),
        "model": model,
        "git_sha7": "abc1234",
        "started_at": "2026-04-23T10:00:00Z",
        "ended_at": "2026-04-23T10:01:00Z",
        "outcome": "success" if success else "abort",
        "success_rate": success,
        "diagnosis_accuracy": diagnosis_accuracy,
        "MTTR_s": mttr,
        "destructive_repair": False,
        "rollback_triggered": False,
        "rollback_success": None,
        "total_input_tokens": 100,
        "total_output_tokens": 50,
        "total_tool_calls": 3,
        "iteration_count": 3,
        "autonomy_level": "full",
        "actions_taken": [],
        "model_version": model,
    }
    (runs_dir / f"{run_id}.json").write_text(json.dumps(record))
    with index_path.open("a") as fh:
        fh.write(json.dumps({"run_id": run_id}) + "\n")


def _make_scenarios_dir(base: Path, scenario_id: str, layer: str = "k8s") -> Path:
    d = base / scenario_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "scenario.yaml").write_text(
        f"id: {scenario_id}\nname: test\nlayer: {layer}\n"
        "root_cause_component: x\nexpected_action: flux_reconcile\n"
        "expected_resolution_path: x\ninject_params: {}\n"
    )
    return base


def test_aggregate_computes_per_model_means(tmp_path: Path) -> None:
    from eval.aggregate import aggregate_runs

    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    index_path = tmp_path / "runs_index.jsonl"
    scenarios_dir = tmp_path / "scenarios"
    _make_scenarios_dir(scenarios_dir, "k8s-1", "k8s")
    _make_scenarios_dir(scenarios_dir, "k8s-2", "k8s")

    for scenario in ("k8s-1", "k8s-2"):
        for model in ("qwen", "deepseek"):
            for seed, mttr in enumerate([10.0, 20.0, 30.0], start=1):
                _write_run(
                    runs_dir,
                    index_path,
                    run_id=f"{scenario}_{seed}_{model}_abc",
                    scenario=scenario,
                    seed=seed,
                    model=model,
                    success=True,
                    mttr=mttr,
                )

    summary = aggregate_runs(runs_dir, index_path, scenarios_dir)

    assert summary["by_model"]["qwen"]["mean_MTTR_s"] == 20.0
    assert summary["by_model"]["qwen"]["success_rate"] == 1.0


def test_aggregate_computes_stdev_with_at_least_two_samples(tmp_path: Path) -> None:
    from eval.aggregate import aggregate_runs

    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    index_path = tmp_path / "runs_index.jsonl"
    scenarios_dir = tmp_path / "scenarios"
    _make_scenarios_dir(scenarios_dir, "k8s-1", "k8s")

    for seed, mttr in enumerate([10.0, 20.0, 30.0], start=1):
        _write_run(
            runs_dir,
            index_path,
            run_id=f"k8s-1_{seed}_qwen_abc",
            scenario="k8s-1",
            seed=seed,
            model="qwen",
            success=True,
            mttr=mttr,
        )

    summary = aggregate_runs(runs_dir, index_path, scenarios_dir)

    expected_std = statistics.stdev([10.0, 20.0, 30.0])
    assert summary["by_model"]["qwen"]["std_MTTR_s"] == expected_std

    # With only 1 sample, stdev should be None
    runs_dir2 = tmp_path / "runs2"
    runs_dir2.mkdir()
    index_path2 = tmp_path / "runs_index2.jsonl"
    _write_run(
        runs_dir2,
        index_path2,
        run_id="k8s-1_1_qwen_abc",
        scenario="k8s-1",
        seed=1,
        model="qwen",
        success=True,
        mttr=15.0,
    )
    summary2 = aggregate_runs(runs_dir2, index_path2, scenarios_dir)
    assert summary2["by_model"]["qwen"]["std_MTTR_s"] is None


def test_aggregate_escalation_accuracy_marks_k8s_scenarios_na(tmp_path: Path) -> None:
    from eval.aggregate import aggregate_runs

    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    index_path = tmp_path / "runs_index.jsonl"
    scenarios_dir = tmp_path / "scenarios"
    _make_scenarios_dir(scenarios_dir, "k8s-1", "k8s")

    _write_run(
        runs_dir,
        index_path,
        run_id="k8s-1_1_qwen_abc",
        scenario="k8s-1",
        seed=1,
        model="qwen",
        success=True,
        mttr=10.0,
        diagnosis_accuracy=True,
    )

    summary = aggregate_runs(runs_dir, index_path, scenarios_dir)
    assert summary["escalation"]["k8s-1"]["accuracy"] is None


def test_aggregate_escalation_accuracy_counts_os_scenarios(tmp_path: Path) -> None:
    from eval.aggregate import aggregate_runs

    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    index_path = tmp_path / "runs_index.jsonl"
    scenarios_dir = tmp_path / "scenarios"
    _make_scenarios_dir(scenarios_dir, "os-1", "os")

    for seed, diag in enumerate([True, True, False], start=1):
        _write_run(
            runs_dir,
            index_path,
            run_id=f"os-1_{seed}_qwen_abc",
            scenario="os-1",
            seed=seed,
            model="qwen",
            success=True,
            mttr=10.0,
            diagnosis_accuracy=diag,
        )

    summary = aggregate_runs(runs_dir, index_path, scenarios_dir)
    esc = summary["escalation"]["os-1"]
    assert esc["accuracy"] == 2 / 3
    assert esc["total"] == 3


def test_write_report_produces_markdown_with_three_tables(tmp_path: Path) -> None:
    from eval.aggregate import write_report

    summary = {
        "by_model": {
            "qwen": {
                "n_runs": 3,
                "success_rate": 1.0,
                "mean_MTTR_s": 20.0,
                "std_MTTR_s": 10.0,
                "diagnosis_accuracy": None,
                "destructive_repair_rate": 0.0,
                "rollback_triggered_rate": 0.0,
                "mean_input_tokens": 100.0,
                "mean_output_tokens": 50.0,
                "mean_tool_calls": 3.0,
                "mean_iteration_count": 3.0,
            },
        },
        "by_scenario": {
            "k8s-1": {
                "n_runs": 3,
                "success_rate": 1.0,
                "mean_MTTR_s": 20.0,
                "std_MTTR_s": 10.0,
            },
        },
        "escalation": {
            "k8s-1": {"layer": "k8s", "accuracy": None},
        },
        "totals": {"n": 3, "n_models": 1, "n_scenarios": 1},
    }

    output_dir = tmp_path / "results"
    write_report(summary, output_dir)

    report = (output_dir / "REPORT.md").read_text()
    assert "## Per-Model Summary" in report
    assert "## Per-Scenario Summary" in report
    assert "## Cross-Layer Escalation Accuracy" in report
    assert (
        "approximate" in report.lower() or "3 seed" in report.lower() or "n=3" in report
    )


def test_write_report_produces_summary_json(tmp_path: Path) -> None:
    from eval.aggregate import write_report

    summary = {
        "by_model": {},
        "by_scenario": {},
        "escalation": {},
        "totals": {"n": 0, "n_models": 0, "n_scenarios": 0},
    }
    output_dir = tmp_path / "results"
    write_report(summary, output_dir)

    json_path = output_dir / "summary.json"
    assert json_path.exists()
    data = json.loads(json_path.read_text())
    for key in ("by_model", "by_scenario", "escalation", "totals"):
        assert key in data


def test_aggregate_cmd_cli_writes_both_files(tmp_path: Path) -> None:
    from eval.cli import cli

    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    index_path = tmp_path / "runs_index.jsonl"
    scenarios_dir = tmp_path / "scenarios"
    _make_scenarios_dir(scenarios_dir, "k8s-1", "k8s")
    output_dir = tmp_path / "results"

    _write_run(
        runs_dir,
        index_path,
        run_id="k8s-1_1_qwen_abc",
        scenario="k8s-1",
        seed=1,
        model="qwen",
        success=True,
        mttr=10.0,
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "aggregate",
            "--runs-dir",
            str(runs_dir),
            "--index",
            str(index_path),
            "--scenarios-dir",
            str(scenarios_dir),
            "--output-dir",
            str(output_dir),
        ],
    )
    assert result.exit_code == 0, result.output
    assert (output_dir / "summary.json").exists()
    assert (output_dir / "REPORT.md").exists()


def test_aggregate_handles_missing_per_run_json_gracefully(tmp_path: Path) -> None:
    from eval.aggregate import aggregate_runs

    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    index_path = tmp_path / "runs_index.jsonl"
    scenarios_dir = tmp_path / "scenarios"
    _make_scenarios_dir(scenarios_dir, "k8s-1", "k8s")

    # Write index entry but NO corresponding JSON file
    with index_path.open("w") as fh:
        fh.write(json.dumps({"run_id": "k8s-1_1_qwen_missing"}) + "\n")

    # Should not raise; skips the missing file
    summary = aggregate_runs(runs_dir, index_path, scenarios_dir)
    assert summary["totals"]["n"] == 0


@pytest.mark.parametrize(
    "literal,expected_bucket",
    [
        ("success", "passed"),
        ("rollback_succeeded", "passed"),
        ("flux_degraded", "agent-failed"),
        ("diagnosis_inconsistent", "agent-failed"),
        ("diagnosis_timeout", "agent-failed"),
        ("budget_exhausted", "agent-failed"),
        ("rollback_failed", "agent-failed"),
        ("quota_exhausted", "agent-failed"),
        ("baseline_degraded", "infra-error"),
        ("abort", "infra-error"),
        ("setup_error", "infra-error"),
        ("gate_failed", "gate-uncertain"),
        ("unknown_literal_xyz", "agent-failed"),
    ],
)
def test_bucket_outcome_mapping(literal: str, expected_bucket: str) -> None:
    from eval.aggregate import _bucket_outcome

    assert _bucket_outcome(literal) == expected_bucket, (
        f"_bucket_outcome({literal!r}) expected {expected_bucket!r}"
    )


def _write_run_with_outcome(
    runs_dir: Path,
    index_path: Path,
    *,
    run_id: str,
    scenario: str,
    outcome: str,
    success_rate: bool = False,
) -> None:
    record = {
        "run_id": run_id,
        "scenario": scenario,
        "seed": "1",
        "model": "test-model",
        "git_sha7": "abc1234",
        "started_at": "2026-05-18T10:00:00Z",
        "ended_at": "2026-05-18T10:01:00Z",
        "outcome": outcome,
        "success_rate": success_rate,
        "diagnosis_accuracy": None,
        "MTTR_s": 10.0 if success_rate else None,
        "destructive_repair": False,
        "rollback_triggered": False,
        "rollback_success": None,
        "total_input_tokens": 100,
        "total_output_tokens": 50,
        "total_tool_calls": 3,
        "iteration_count": 2,
        "autonomy_level": "full",
        "actions_taken": [],
        "model_version": "test-model",
    }
    (runs_dir / f"{run_id}.json").write_text(json.dumps(record))
    with index_path.open("a") as fh:
        fh.write(json.dumps({"run_id": run_id}) + "\n")


def test_write_report_includes_per_row_outcome_literal_and_rollup(
    tmp_path: Path,
) -> None:
    from eval.aggregate import aggregate_runs, write_report

    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    index_path = tmp_path / "runs_index.jsonl"
    scenarios_dir = tmp_path / "scenarios"
    output_dir = tmp_path / "results"

    _make_scenarios_dir(scenarios_dir, "k8s-1", "k8s")
    _make_scenarios_dir(scenarios_dir, "k8s-2", "k8s")
    _make_scenarios_dir(scenarios_dir, "os-1", "os")
    _make_scenarios_dir(scenarios_dir, "ingress-1", "k8s")

    _write_run_with_outcome(
        runs_dir,
        index_path,
        run_id="k8s-1_1_test-model_abc",
        scenario="k8s-1",
        outcome="success",
        success_rate=True,
    )
    _write_run_with_outcome(
        runs_dir,
        index_path,
        run_id="k8s-2_1_test-model_abc",
        scenario="k8s-2",
        outcome="gate_failed",
    )
    _write_run_with_outcome(
        runs_dir,
        index_path,
        run_id="os-1_1_test-model_abc",
        scenario="os-1",
        outcome="baseline_degraded",
    )
    _write_run_with_outcome(
        runs_dir,
        index_path,
        run_id="ingress-1_1_test-model_abc",
        scenario="ingress-1",
        outcome="flux_degraded",
    )

    summary = aggregate_runs(runs_dir, index_path, scenarios_dir)
    write_report(summary, output_dir)

    report = (output_dir / "REPORT.md").read_text()

    assert "Outcome" in report

    assert "success" in report
    assert "gate_failed" in report
    assert "baseline_degraded" in report
    assert "flux_degraded" in report

    assert "passed" in report
    assert "agent-failed" in report
    assert "infra-error" in report
    assert "gate-uncertain" in report

    rollup_pattern = (
        r"\d+/\d+ passed,\s*\d+/\d+ out-of-scope,\s*\d+/\d+ agent-failed,"
        r"\s*\d+/\d+ infra-error,\s*\d+/\d+ gate-uncertain,"
        r"\s*\d+/\d+ awaiting-review,\s*\d+/\d+ not-run"
    )
    assert re.search(rollup_pattern, report), (
        f"expected bucket rollup line in REPORT.md; got:\n{report}"
    )


def test_write_step_summary_uses_raw_literal_and_bucket_rollup(
    tmp_path: Path,
) -> None:
    from eval.aggregate import write_step_summary

    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    index_path = tmp_path / "runs_index.jsonl"
    scenarios_dir = tmp_path / "scenarios"
    output_dir = tmp_path / "results"

    _make_scenarios_dir(scenarios_dir, "k8s-1", "k8s")
    _make_scenarios_dir(scenarios_dir, "k8s-2", "k8s")
    _make_scenarios_dir(scenarios_dir, "os-1", "os")

    _write_run_with_outcome(
        runs_dir,
        index_path,
        run_id="k8s-1_1_test-model_abc",
        scenario="k8s-1",
        outcome="success",
        success_rate=True,
    )
    _write_run_with_outcome(
        runs_dir,
        index_path,
        run_id="k8s-2_1_test-model_abc",
        scenario="k8s-2",
        outcome="rollback_failed",
    )
    _write_run_with_outcome(
        runs_dir,
        index_path,
        run_id="os-1_1_test-model_abc",
        scenario="os-1",
        outcome="setup_error",
    )

    write_step_summary(runs_dir, index_path, output_dir, scenarios_dir)

    summary_text = (output_dir / "step_summary.md").read_text()

    assert "success" in summary_text
    assert "rollback_failed" in summary_text
    assert "setup_error" in summary_text

    rollup_pattern = (
        r"\d+/\d+ passed,\s*\d+/\d+ out-of-scope,\s*\d+/\d+ agent-failed,"
        r"\s*\d+/\d+ infra-error,\s*\d+/\d+ gate-uncertain,"
        r"\s*\d+/\d+ awaiting-review,\s*\d+/\d+ not-run"
    )
    assert re.search(rollup_pattern, summary_text), (
        f"expected bucket rollup line in step_summary.md; got:\n{summary_text}"
    )


def test_count_buckets_out_of_scope_for_success_with_false_success_rate(
    tmp_path: Path,
) -> None:
    from eval.aggregate import _count_buckets

    records = [
        {"outcome": "success", "success_rate": False},
        {"outcome": "success", "success_rate": True},
        {"outcome": "flux_degraded", "success_rate": False},
    ]
    counts = _count_buckets(records)
    assert counts["out-of-scope"] == 1
    assert counts["passed"] == 1
    assert counts["agent-failed"] == 1


def test_count_buckets_out_of_scope_absent_when_no_forbidden_violations(
    tmp_path: Path,
) -> None:
    from eval.aggregate import _count_buckets

    records = [
        {"outcome": "success", "success_rate": True},
        {"outcome": "success", "success_rate": True},
    ]
    counts = _count_buckets(records)
    assert counts["out-of-scope"] == 0
    assert counts["passed"] == 2


def test_count_buckets_escalated_correct_counts_as_passed() -> None:
    from eval.aggregate import _count_buckets

    records = [
        {"outcome": "escalated", "success_rate": True},
        {"outcome": "escalated", "success_rate": False},
        {"outcome": "escalated", "success_rate": None},
    ]
    counts = _count_buckets(records)
    assert counts["passed"] == 1
    assert counts["agent-failed"] == 2
    assert counts["not-run"] == 0


def _make_rollback_scenarios_dir(base: Path, scenario_id: str) -> Path:
    d = base / scenario_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "scenario.yaml").write_text(
        f"id: {scenario_id}\nname: test\nlayer: k8s\n"
        "root_cause_component: x\nexpected_action: git_commit_k8s\n"
        "expected_resolution_path: x\nexpected_outcome: rollback_succeeded\n"
        "inject_params: {}\n"
    )
    return base


def test_expected_outcome_marks_rollback_succeeded_as_success(tmp_path: Path) -> None:
    from eval.aggregate import aggregate_runs

    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    index_path = tmp_path / "runs_index.jsonl"
    scenarios_dir = tmp_path / "scenarios"
    _make_rollback_scenarios_dir(scenarios_dir, "k8s-rollback-1")

    _write_run_with_outcome(
        runs_dir,
        index_path,
        run_id="k8s-rollback-1_1_test-model_abc",
        scenario="k8s-rollback-1",
        outcome="rollback_succeeded",
        success_rate=False,
    )

    summary = aggregate_runs(runs_dir, index_path, scenarios_dir)
    assert summary["by_scenario"]["k8s-rollback-1"]["success_rate"] == 1.0


def test_expected_outcome_does_not_mark_mismatched_outcome(tmp_path: Path) -> None:
    from eval.aggregate import aggregate_runs

    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    index_path = tmp_path / "runs_index.jsonl"
    scenarios_dir = tmp_path / "scenarios"
    _make_rollback_scenarios_dir(scenarios_dir, "k8s-rollback-1")

    _write_run_with_outcome(
        runs_dir,
        index_path,
        run_id="k8s-rollback-1_1_test-model_abc",
        scenario="k8s-rollback-1",
        outcome="rollback_failed",
        success_rate=False,
    )

    summary = aggregate_runs(runs_dir, index_path, scenarios_dir)
    assert summary["by_scenario"]["k8s-rollback-1"]["success_rate"] == 0.0


def test_count_buckets_not_run_counts_unexecuted_planned_scenarios() -> None:
    from eval.aggregate import _count_buckets

    records = [
        {"outcome": "success", "success_rate": True},
        {"outcome": "escalated", "success_rate": True},
    ]
    counts = _count_buckets(records, n_planned=5)
    assert counts["passed"] == 2
    assert counts["not-run"] == 3
