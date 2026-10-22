"""Shared fixtures for eval harness tests."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def isolated_repo_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VIGIL_REPO_ROOT", raising=False)


@pytest.fixture(scope="session")
def scenarios_dir() -> Path:
    """The canonical eval/scenarios directory in this repo."""
    return REPO_ROOT / "eval" / "scenarios"


@pytest.fixture()
def tmp_scenarios_dir(tmp_path: Path) -> Path:
    """Empty per-test scenarios dir for bad-YAML injection tests."""
    d = tmp_path / "scenarios"
    d.mkdir()
    return d
