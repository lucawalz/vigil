"""Scenario definitions for the vigil eval framework."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field


class ScenarioDefinition(BaseModel):
    id: str
    name: str
    layer: Literal["k8s", "os", "cross", "boundary"]
    root_cause_layer: Literal["k8s", "os", "cross", "boundary"]
    root_cause_component: str
    correct_action_class: str = Field(
        pattern="^(apply_patch|rollout_undo|rebuild_nixos|escalate)$"
    )
    expected_resolution_path: str
    inject_params: dict[str, Any] = Field(default_factory=dict)


def load_scenarios(scenarios_dir: Path) -> list[ScenarioDefinition]:
    """Load every scenarios/{id}/scenario.yaml into a ScenarioDefinition."""
    scenarios: list[ScenarioDefinition] = []
    for yaml_path in sorted(scenarios_dir.glob("*/scenario.yaml")):
        with yaml_path.open() as f:
            data = yaml.safe_load(f)
        scenarios.append(ScenarioDefinition.model_validate(data))
    return scenarios
