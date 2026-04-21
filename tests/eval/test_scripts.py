"""Static validation for K8s scenario injection/reset scripts (EVAL-02, EVAL-03)."""
from __future__ import annotations

import stat
import subprocess
from pathlib import Path

import pytest

K8S_SCENARIO_IDS = ("k8s-1", "k8s-2", "k8s-3", "k8s-4", "k8s-5")


def _scripts_for(scenarios_dir: Path) -> list[Path]:
    paths: list[Path] = []
    for sid in K8S_SCENARIO_IDS:
        paths.append(scenarios_dir / sid / "inject.sh")
        paths.append(scenarios_dir / sid / "reset.sh")
    return paths


@pytest.mark.parametrize("sid", K8S_SCENARIO_IDS)
def test_all_k8s_scenarios_have_both_scripts(scenarios_dir: Path, sid: str) -> None:
    assert (scenarios_dir / sid / "inject.sh").is_file()
    assert (scenarios_dir / sid / "reset.sh").is_file()


def test_all_k8s_scripts_have_shebang(scenarios_dir: Path) -> None:
    for path in _scripts_for(scenarios_dir):
        first_line = path.read_text().splitlines()[0]
        assert first_line == "#!/usr/bin/env bash", (
            f"{path}: bad shebang {first_line!r}"
        )


def test_all_k8s_scripts_have_safety_flags(scenarios_dir: Path) -> None:
    for path in _scripts_for(scenarios_dir):
        head = path.read_text().splitlines()[:10]
        assert "set -euo pipefail" in head, (
            f"{path}: missing `set -euo pipefail` in first 10 lines"
        )


def test_all_k8s_scripts_accept_seed_arg(scenarios_dir: Path) -> None:
    for path in _scripts_for(scenarios_dir):
        body = path.read_text()
        assert 'SEED="${1:-1}"' in body, (
            f'{path}: missing SEED="${{1:-1}}" convention'
        )


def test_all_k8s_scripts_executable(scenarios_dir: Path) -> None:
    for path in _scripts_for(scenarios_dir):
        mode = path.stat().st_mode
        assert mode & stat.S_IXUSR, f"{path}: user-execute bit not set"


def test_all_reset_scripts_apply_manifests(scenarios_dir: Path) -> None:
    for sid in K8S_SCENARIO_IDS:
        reset_sh = scenarios_dir / sid / "reset.sh"
        assert "kubectl apply -f" in reset_sh.read_text(), (
            f"{reset_sh}: missing kubectl apply -f"
        )


def test_all_reset_scripts_resume_flux(scenarios_dir: Path) -> None:
    for sid in K8S_SCENARIO_IDS:
        reset_sh = scenarios_dir / sid / "reset.sh"
        body = reset_sh.read_text()
        assert "flux resume kustomization flux-system" in body, (
            f"{reset_sh}: missing flux resume recovery step"
        )


@pytest.mark.parametrize("script_name", ["inject.sh", "reset.sh"])
@pytest.mark.parametrize("sid", K8S_SCENARIO_IDS)
def test_all_k8s_scripts_syntax_valid(
    scenarios_dir: Path, sid: str, script_name: str
) -> None:
    path = scenarios_dir / sid / script_name
    # bash -n = parse-only, no execution. Fails with non-zero on syntax error.
    result = subprocess.run(
        ["bash", "-n", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"{path}: bash -n failed: {result.stderr}"
