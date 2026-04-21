"""Tests for ScenarioDefinition model and load_scenarios() loader."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from eval.scenario import ScenarioDefinition, load_scenarios
from pydantic import ValidationError


@pytest.fixture()
def real_scenarios(scenarios_dir: Path) -> list[ScenarioDefinition]:
    if (
        not scenarios_dir.exists()
        or len(list(scenarios_dir.glob("*/scenario.yaml"))) < 12
    ):
        pytest.skip("scenarios directory not fully populated yet")
    return load_scenarios(scenarios_dir)


def test_load_all_scenarios(real_scenarios: list[ScenarioDefinition]) -> None:
    assert len(real_scenarios) == 12
    ids = [s.id for s in real_scenarios]
    assert sorted(ids) == [
        "boundary-1", "cross-1", "cross-2", "cross-3",
        "k8s-1", "k8s-2", "k8s-3", "k8s-4", "k8s-5",
        "os-1", "os-2", "os-3",
    ]


def test_required_ground_truth_fields_present(
    real_scenarios: list[ScenarioDefinition],
) -> None:
    for s in real_scenarios:
        assert s.root_cause_layer, f"{s.id}: root_cause_layer is empty"
        assert s.root_cause_component, f"{s.id}: root_cause_component is empty"
        assert s.correct_action_class, f"{s.id}: correct_action_class is empty"
        assert s.expected_resolution_path, f"{s.id}: expected_resolution_path is empty"


def test_rejects_missing_required_field(tmp_scenarios_dir: Path) -> None:
    scenario_dir = tmp_scenarios_dir / "bad-1"
    scenario_dir.mkdir()
    bad_yaml = {
        "id": "bad-1",
        "name": "missing-component",
        "layer": "k8s",
        "root_cause_layer": "k8s",
        # root_cause_component intentionally omitted
        "correct_action_class": "rollout_undo",
        "expected_resolution_path": "diagnosis -> rollout_undo",
    }
    (scenario_dir / "scenario.yaml").write_text(yaml.dump(bad_yaml))
    with pytest.raises(ValidationError):
        load_scenarios(tmp_scenarios_dir)


def test_rejects_invalid_correct_action_class(tmp_scenarios_dir: Path) -> None:
    scenario_dir = tmp_scenarios_dir / "bad-1"
    scenario_dir.mkdir()
    bad_yaml = {
        "id": "bad-1",
        "name": "bad-action",
        "layer": "k8s",
        "root_cause_layer": "k8s",
        "root_cause_component": "Deployment/vigil-app",
        "correct_action_class": "purge_database",
        "expected_resolution_path": "diagnosis -> purge_database",
    }
    (scenario_dir / "scenario.yaml").write_text(yaml.dump(bad_yaml))
    with pytest.raises(ValidationError):
        load_scenarios(tmp_scenarios_dir)


def test_rejects_invalid_layer(tmp_scenarios_dir: Path) -> None:
    scenario_dir = tmp_scenarios_dir / "bad-1"
    scenario_dir.mkdir()
    bad_yaml = {
        "id": "bad-1",
        "name": "bad-layer",
        "layer": "quantum",
        "root_cause_layer": "k8s",
        "root_cause_component": "Deployment/vigil-app",
        "correct_action_class": "apply_patch",
        "expected_resolution_path": "diagnosis -> apply_patch",
    }
    (scenario_dir / "scenario.yaml").write_text(yaml.dump(bad_yaml))
    with pytest.raises(ValidationError):
        load_scenarios(tmp_scenarios_dir)


def test_roundtrip_model_dump_validate() -> None:
    original = ScenarioDefinition(
        id="k8s-1",
        name="wrong-image-tag",
        layer="k8s",
        root_cause_layer="k8s",
        root_cause_component=(
            "Deployment/vigil-app image nginx:bad-tag-v9 (ImagePullBackOff)"
        ),
        correct_action_class="rollout_undo",
        expected_resolution_path=(
            "diagnosis -> flux_suspend -> rollout_undo"
            " -> watchdog_confirm -> flux_resume"
        ),
        inject_params={"namespace": "default", "deployment": "vigil-app"},
    )
    dumped = original.model_dump()
    restored = ScenarioDefinition.model_validate(dumped)
    assert restored == original


def test_inject_params_preserved(tmp_scenarios_dir: Path) -> None:
    scenario_dir = tmp_scenarios_dir / "k8s-test"
    scenario_dir.mkdir()
    scenario_yaml = {
        "id": "k8s-test",
        "name": "test-inject",
        "layer": "k8s",
        "root_cause_layer": "k8s",
        "root_cause_component": "Deployment/vigil-app",
        "correct_action_class": "apply_patch",
        "expected_resolution_path": "diagnosis -> apply_patch",
        "inject_params": {
            "namespace": "default",
            "deployment": "vigil-app",
        },
    }
    (scenario_dir / "scenario.yaml").write_text(yaml.dump(scenario_yaml))
    scenarios = load_scenarios(tmp_scenarios_dir)
    assert len(scenarios) == 1
    assert scenarios[0].inject_params["namespace"] == "default"
    assert scenarios[0].inject_params["deployment"] == "vigil-app"
