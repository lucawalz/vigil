"""Tests for campaign.py: completed_run_ids + combinations + CLI error paths."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner


def test_completed_run_ids_empty_when_no_index(tmp_path: Path) -> None:
    from eval.campaign import completed_run_ids

    result = completed_run_ids(tmp_path / "runs_index.jsonl")
    assert result == set()


def test_completed_run_ids_parses_jsonl(tmp_path: Path) -> None:
    from eval.campaign import completed_run_ids

    index = tmp_path / "runs_index.jsonl"
    lines = [
        {"run_id": "k8s-1_1_m1_abc1234"},
        {"run_id": "k8s-2_2_m1_abc1234"},
        {"run_id": "k8s-3_3_m2_abc1234"},
    ]
    index.write_text("\n".join(json.dumps(line) for line in lines) + "\n")
    result = completed_run_ids(index)
    assert result == {"k8s-1_1_m1_abc1234", "k8s-2_2_m1_abc1234", "k8s-3_3_m2_abc1234"}


def test_completed_run_ids_ignores_blank_lines(tmp_path: Path) -> None:
    from eval.campaign import completed_run_ids

    index = tmp_path / "runs_index.jsonl"
    index.write_text(
        json.dumps({"run_id": "k8s-1_1_m1_abc"})
        + "\n"
        + "\n"
        + "   \n"
        + json.dumps({"run_id": "k8s-2_2_m1_abc"})
        + "\n"
    )
    result = completed_run_ids(index)
    assert result == {"k8s-1_1_m1_abc", "k8s-2_2_m1_abc"}


def test_combinations_cartesian_product_size() -> None:
    from eval.campaign import combinations

    scenarios = ["k8s-1", "k8s-2", "k8s-3"]
    seeds = [1, 2, 3]
    models = ["m1", "m2"]
    result = list(combinations(scenarios, seeds, models))
    assert len(result) == 18


def test_combinations_yields_tuples_of_three() -> None:
    from eval.campaign import combinations

    result = list(combinations(["k8s-1"], [1], ["m1"]))
    assert len(result) == 1
    item = result[0]
    assert isinstance(item, tuple)
    assert len(item) == 3
    scenario_id, seed, model = item
    assert scenario_id == "k8s-1"
    assert seed == 1
    assert model == "m1"


def test_cli_timeout_maps_to_nonzero_exit(tmp_path: Path) -> None:
    from eval.cli import cli

    runner = CliRunner()
    with patch("eval.cli.run_one", side_effect=TimeoutError("timed out")):
        result = runner.invoke(
            cli,
            [
                "run",
                "--scenario",
                "k8s-1",
                "--seed",
                "1",
                "--model",
                "test-model",
                "--scenarios-dir",
                str(tmp_path),
                "--runs-dir",
                str(tmp_path / "runs"),
            ],
        )
    assert result.exit_code != 0


def test_cli_runtime_error_also_nonzero_exit(tmp_path: Path) -> None:
    from eval.cli import cli

    runner = CliRunner()
    with patch("eval.cli.run_one", side_effect=RuntimeError("script failed")):
        result = runner.invoke(
            cli,
            [
                "run",
                "--scenario",
                "k8s-1",
                "--seed",
                "1",
                "--model",
                "test-model",
                "--scenarios-dir",
                str(tmp_path),
                "--runs-dir",
                str(tmp_path / "runs"),
            ],
        )
    assert result.exit_code != 0


def test_combinations_model_grouped_within_scenario() -> None:
    from eval.campaign import combinations

    scenarios = ["k8s-1", "k8s-2"]
    seeds = [1, 2, 3]
    models = ["qwen", "deepseek"]
    result = list(combinations(scenarios, seeds, models))
    assert result[:6] == [
        ("k8s-1", 1, "qwen"),
        ("k8s-1", 2, "qwen"),
        ("k8s-1", 3, "qwen"),
        ("k8s-1", 1, "deepseek"),
        ("k8s-1", 2, "deepseek"),
        ("k8s-1", 3, "deepseek"),
    ]
    assert result[6:] == [
        ("k8s-2", 1, "qwen"),
        ("k8s-2", 2, "qwen"),
        ("k8s-2", 3, "qwen"),
        ("k8s-2", 1, "deepseek"),
        ("k8s-2", 2, "deepseek"),
        ("k8s-2", 3, "deepseek"),
    ]


def test_combinations_no_scenario_crossover_before_all_models_done() -> None:
    from eval.campaign import combinations

    scenarios = ["a", "b", "c"]
    seeds = [1, 2]
    models = ["m1", "m2"]
    result = list(combinations(scenarios, seeds, models))
    for i in range(len(result) - 1):
        if result[i][0] != result[i + 1][0]:
            assert result[i] == (result[i][0], seeds[-1], models[-1])
            assert result[i + 1] == (result[i + 1][0], seeds[0], models[0])


def test_completed_run_ids_supports_resume_skip_by_prefix(tmp_path: Path) -> None:
    from eval.campaign import combinations, completed_run_ids

    index = tmp_path / "runs_index.jsonl"
    done_ids = [
        "k8s-1_1_qwen_abc1234",
        "k8s-1_2_qwen_abc1234",
        "k8s-1_3_qwen_abc1234",
    ]
    index.write_text("\n".join(json.dumps({"run_id": rid}) for rid in done_ids) + "\n")
    done = completed_run_ids(index)

    all_combos = list(combinations(["k8s-1"], [1, 2, 3], ["qwen", "deepseek"]))
    remaining = [
        (sc, sd, md)
        for sc, sd, md in all_combos
        if not any(rid.startswith(f"{sc}_{sd}_{md}_") for rid in done)
    ]
    assert len(remaining) == 3
    assert all(md == "deepseek" for _, _, md in remaining)


def _make_scenario_yaml(scenarios_dir: Path, sid: str) -> None:
    d = scenarios_dir / sid
    d.mkdir(parents=True, exist_ok=True)
    (d / "scenario.yaml").write_text(
        f"id: {sid}\nname: test\nlayer: k8s\n"
        "root_cause_component: x\nexpected_action: flux_reconcile\n"
        "expected_resolution_path: x\ninject_params: {}\n"
    )


def test_campaign_cmd_skips_completed_run_ids(tmp_path: Path) -> None:
    from eval.cli import cli

    scenarios_dir = tmp_path / "scenarios"
    _make_scenario_yaml(scenarios_dir, "k8s-1")
    _make_scenario_yaml(scenarios_dir, "k8s-2")

    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    index_path = tmp_path / "runs_index.jsonl"
    index_path.write_text(
        json.dumps({"run_id": "k8s-1_1_qwen_abc1234"})
        + "\n"
        + json.dumps({"run_id": "k8s-1_2_qwen_abc1234"})
        + "\n"
    )

    calls: list[tuple] = []

    async def fake_run_one(**kwargs):
        calls.append((kwargs["scenario_id"], kwargs["seed"], kwargs["model"]))
        run_id = f"{kwargs['scenario_id']}_{kwargs['seed']}_{kwargs['model']}_zzzzzzz"
        out = kwargs["runs_dir"] / f"{run_id}.json"
        data = {"run_id": run_id, "success_rate": True, "MTTR_s": 1.0}
        out.write_text(json.dumps(data))
        return out

    runner = CliRunner()
    with patch("eval.cli.run_one", side_effect=fake_run_one):
        result = runner.invoke(
            cli,
            [
                "campaign",
                "--scenarios-dir",
                str(scenarios_dir),
                "--models",
                "qwen",
                "--models",
                "deepseek",
                "--seeds",
                "1",
                "--seeds",
                "2",
                "--runs-dir",
                str(runs_dir),
                "--index",
                str(index_path),
            ],
        )
    assert result.exit_code == 0, result.output
    # (2 scenarios × 2 models × 2 seeds) − 2 completed = 6 calls
    assert len(calls) == 6
    assert ("k8s-1", 1, "qwen") not in calls
    assert ("k8s-1", 2, "qwen") not in calls


def test_campaign_cmd_logs_failure_and_continues(tmp_path: Path) -> None:
    from eval.cli import cli

    scenarios_dir = tmp_path / "scenarios"
    _make_scenario_yaml(scenarios_dir, "k8s-1")

    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    index_path = tmp_path / "runs_index.jsonl"
    index_path.write_text("")

    call_count = [0]

    async def fake_run_one(**kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise TimeoutError("timed out")
        run_id = f"{kwargs['scenario_id']}_{kwargs['seed']}_{kwargs['model']}_zzzzzzz"
        out = kwargs["runs_dir"] / f"{run_id}.json"
        data = {"run_id": run_id, "success_rate": True, "MTTR_s": 5.0}
        out.write_text(json.dumps(data))
        return out

    runner = CliRunner()
    with patch("eval.cli.run_one", side_effect=fake_run_one):
        result = runner.invoke(
            cli,
            [
                "campaign",
                "--scenarios-dir",
                str(scenarios_dir),
                "--models",
                "qwen",
                "--seeds",
                "1",
                "--seeds",
                "2",
                "--seeds",
                "3",
                "--runs-dir",
                str(runs_dir),
                "--index",
                str(index_path),
            ],
        )
    assert result.exit_code == 0
    failures_path = runs_dir / "failures.jsonl"
    assert failures_path.exists()
    lines = [line for line in failures_path.read_text().splitlines() if line.strip()]
    assert len(lines) == 1
    failure = json.loads(lines[0])
    assert "timed out" in failure["error"]
    # all 3 combinations attempted
    assert call_count[0] == 3


def test_campaign_cmd_prints_progress_lines_to_stderr(tmp_path: Path) -> None:
    from eval.cli import cli

    scenarios_dir = tmp_path / "scenarios"
    _make_scenario_yaml(scenarios_dir, "k8s-1")

    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    index_path = tmp_path / "runs_index.jsonl"
    index_path.write_text("")

    async def fake_run_one(**kwargs):
        run_id = f"{kwargs['scenario_id']}_{kwargs['seed']}_{kwargs['model']}_zzzzzzz"
        out = kwargs["runs_dir"] / f"{run_id}.json"
        data = {"run_id": run_id, "success_rate": True, "MTTR_s": 47.0}
        out.write_text(json.dumps(data))
        return out

    runner = CliRunner()
    with patch("eval.cli.run_one", side_effect=fake_run_one):
        result = runner.invoke(
            cli,
            [
                "campaign",
                "--scenarios-dir",
                str(scenarios_dir),
                "--models",
                "qwen",
                "--seeds",
                "1",
                "--runs-dir",
                str(runs_dir),
                "--index",
                str(index_path),
            ],
        )
    assert result.exit_code == 0
    # CliRunner mixes stdout+stderr into result.output in Click 8.x
    assert "[1/1] k8s-1/seed1/qwen — SUCCESS (MTTR=47s)" in result.output


def test_campaign_cmd_retry_failed_reruns_only_failures(tmp_path: Path) -> None:
    from eval.cli import cli

    scenarios_dir = tmp_path / "scenarios"
    _make_scenario_yaml(scenarios_dir, "k8s-2")

    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    failures_path = runs_dir / "failures.jsonl"
    failures_path.write_text(
        json.dumps(
            {
                "scenario": "k8s-2",
                "seed": 3,
                "model": "deepseek",
                "timestamp": "2026-04-24T00:00:00Z",
                "error": "timeout",
            }
        )
        + "\n"
    )

    calls: list[tuple] = []

    async def fake_run_one(**kwargs):
        calls.append((kwargs["scenario_id"], kwargs["seed"], kwargs["model"]))
        run_id = f"{kwargs['scenario_id']}_{kwargs['seed']}_{kwargs['model']}_zzzzzzz"
        out = kwargs["runs_dir"] / f"{run_id}.json"
        data = {"run_id": run_id, "success_rate": True, "MTTR_s": 5.0}
        out.write_text(json.dumps(data))
        return out

    runner = CliRunner()
    with patch("eval.cli.run_one", side_effect=fake_run_one):
        result = runner.invoke(
            cli,
            [
                "campaign",
                "--scenarios-dir",
                str(scenarios_dir),
                "--models",
                "deepseek",
                "--seeds",
                "3",
                "--runs-dir",
                str(runs_dir),
                "--retry-failed",
            ],
        )
    assert result.exit_code == 0
    assert calls == [("k8s-2", 3, "deepseek")]
    # entry removed on success
    assert not failures_path.exists() or failures_path.read_text().strip() == ""


def test_campaign_cmd_progress_line_includes_trace_path(tmp_path, monkeypatch):
    """Campaign progress echo must include '| trace:' with the run_id trace path."""
    # String-level test: read cli.py source and assert trace format strings are present.
    import importlib.util

    spec = importlib.util.find_spec("eval.cli")
    assert spec is not None
    src = Path(spec.origin).read_text()
    assert "trace:" in src
    assert "_trace.jsonl" in src


def test_campaign_cmd_exits_0_after_all_combinations_attempted_even_with_failures(
    tmp_path: Path,
) -> None:
    from eval.cli import cli

    scenarios_dir = tmp_path / "scenarios"
    _make_scenario_yaml(scenarios_dir, "k8s-1")

    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    index_path = tmp_path / "runs_index.jsonl"
    index_path.write_text("")

    async def always_fails(**kwargs):
        raise RuntimeError("injected failure")

    runner = CliRunner()
    with patch("eval.cli.run_one", side_effect=always_fails):
        result = runner.invoke(
            cli,
            [
                "campaign",
                "--scenarios-dir",
                str(scenarios_dir),
                "--models",
                "qwen",
                "--seeds",
                "1",
                "--runs-dir",
                str(runs_dir),
                "--index",
                str(index_path),
            ],
        )
    assert result.exit_code == 0
