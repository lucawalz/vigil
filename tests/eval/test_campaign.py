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
