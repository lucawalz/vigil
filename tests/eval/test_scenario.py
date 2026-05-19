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
        or len(list(scenarios_dir.glob("*/scenario.yaml"))) < 26
    ):
        pytest.skip("scenarios directory not fully populated yet")
    return load_scenarios(scenarios_dir)


def test_load_all_scenarios(real_scenarios: list[ScenarioDefinition]) -> None:
    assert len(real_scenarios) == 26
    ids = [s.id for s in real_scenarios]
    assert sorted(ids) == [
        "boundary-1",
        "boundary-2",
        "boundary-3",
        "boundary-4",
        "cross-1",
        "cross-2",
        "cross-3",
        "ingress-1",
        "k8s-1",
        "k8s-1g",
        "k8s-2",
        "k8s-2g",
        "k8s-3",
        "k8s-3g",
        "k8s-4",
        "k8s-4g",
        "k8s-5",
        "k8s-5g",
        "os-1",
        "os-1g",
        "os-2",
        "os-2g",
        "os-3",
        "os-3g",
        "pg-1",
        "redis-1",
    ]


def test_required_ground_truth_fields_present(
    real_scenarios: list[ScenarioDefinition],
) -> None:
    for s in real_scenarios:
        assert s.expected_action, f"{s.id}: expected_action is empty"
        assert s.root_cause_component, f"{s.id}: root_cause_component is empty"
        assert s.expected_resolution_path, f"{s.id}: expected_resolution_path is empty"


def test_rejects_missing_required_field(tmp_scenarios_dir: Path) -> None:
    scenario_dir = tmp_scenarios_dir / "bad-1"
    scenario_dir.mkdir()
    bad_yaml = {
        "id": "bad-1",
        "name": "missing-component",
        "layer": "k8s",
        # root_cause_component intentionally omitted
        "expected_action": "flux_reconcile",
        "expected_resolution_path": "diagnosis -> flux_reconcile",
    }
    (scenario_dir / "scenario.yaml").write_text(yaml.dump(bad_yaml))
    with pytest.raises(ValidationError):
        load_scenarios(tmp_scenarios_dir)


def test_rejects_missing_expected_action(tmp_scenarios_dir: Path) -> None:
    scenario_dir = tmp_scenarios_dir / "bad-1"
    scenario_dir.mkdir()
    bad_yaml = {
        "id": "bad-1",
        "name": "no-expected-action",
        "layer": "k8s",
        "root_cause_component": "Deployment/vigil-app",
        "expected_resolution_path": "diagnosis -> flux_reconcile",
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
        "root_cause_component": "Deployment/vigil-app",
        "expected_action": "flux_reconcile",
        "expected_resolution_path": "diagnosis -> flux_reconcile",
    }
    (scenario_dir / "scenario.yaml").write_text(yaml.dump(bad_yaml))
    with pytest.raises(ValidationError):
        load_scenarios(tmp_scenarios_dir)


def test_roundtrip_model_dump_validate() -> None:
    original = ScenarioDefinition(
        id="k8s-1",
        name="wrong-image-tag",
        layer="k8s",
        root_cause_component=(
            "Deployment/vigil-app image nginx:bad-tag-v9 (ImagePullBackOff)"
        ),
        expected_action="flux_reconcile",
        expected_resolution_path=(
            "diagnosis -> flux_reconcile -> gate_pass -> watchdog_confirm"
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
        "root_cause_component": "Deployment/vigil-app",
        "expected_action": "flux_reconcile",
        "expected_resolution_path": "diagnosis -> flux_reconcile",
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


def test_accepts_flux_reconcile_expected_action(tmp_scenarios_dir: Path) -> None:
    scenario_dir = tmp_scenarios_dir / "k8s-test"
    scenario_dir.mkdir()
    scenario_yaml = {
        "id": "k8s-test",
        "name": "test-flux-reconcile",
        "layer": "k8s",
        "root_cause_component": "Deployment/vigil-app",
        "expected_action": "flux_reconcile",
        "expected_resolution_path": (
            "diagnosis -> flux_reconcile -> gate_pass -> watchdog_confirm"
        ),
    }
    (scenario_dir / "scenario.yaml").write_text(yaml.dump(scenario_yaml))
    scenarios = load_scenarios(tmp_scenarios_dir)
    assert scenarios[0].expected_action == "flux_reconcile"


def test_forbidden_actions_defaults_to_empty_list() -> None:
    s = ScenarioDefinition(
        id="k8s-1",
        name="x",
        layer="k8s",
        root_cause_component="Deployment/vigil-app",
        expected_action="flux_reconcile",
        expected_resolution_path="diagnosis -> flux_reconcile",
    )
    assert s.forbidden_actions == []


def test_accepts_nixos_rebuild_expected_action(tmp_scenarios_dir: Path) -> None:
    scenario_dir = tmp_scenarios_dir / "os-test"
    scenario_dir.mkdir()
    scenario_yaml = {
        "id": "os-test",
        "name": "nixos-rebuild-test",
        "layer": "os",
        "root_cause_component": "NixOS service",
        "expected_action": "nixos_rebuild",
        "expected_resolution_path": "diagnosis -> nixos_rebuild -> watchdog_confirm",
    }
    (scenario_dir / "scenario.yaml").write_text(yaml.dump(scenario_yaml))
    scenarios = load_scenarios(tmp_scenarios_dir)
    assert scenarios[0].expected_action == "nixos_rebuild"


def test_forbidden_actions_roundtrips_through_yaml(tmp_scenarios_dir: Path) -> None:
    scenario_dir = tmp_scenarios_dir / "b1"
    scenario_dir.mkdir()
    (scenario_dir / "scenario.yaml").write_text(
        yaml.dump(
            {
                "id": "b1",
                "name": "x",
                "layer": "boundary",
                "root_cause_component": "imagePullSecret",
                "expected_action": "flux_reconcile",
                "expected_resolution_path": "diagnosis -> flux_reconcile",
                "forbidden_actions": ["switch_generation"],
            }
        )
    )
    scenarios = load_scenarios(tmp_scenarios_dir)
    assert scenarios[0].forbidden_actions == ["switch_generation"]
