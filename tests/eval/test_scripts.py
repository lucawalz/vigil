"""Static validation for scenario injection/reset scripts (EVAL-02, EVAL-03)."""

from __future__ import annotations

import stat
import subprocess
from pathlib import Path

import pytest

K8S_SCENARIO_IDS = ("k8s-1", "k8s-2", "k8s-3", "k8s-4", "k8s-5")
OS_SCENARIO_IDS = ("os-1", "os-2", "os-3")
CROSS_SCENARIO_IDS = ("cross-1", "cross-2", "cross-3")
BOUNDARY_SCENARIO_IDS = ("boundary-1",)
PROD_SIM_SCENARIO_IDS = ("pg-1", "redis-1", "ingress-1")
ALL_SCENARIO_IDS = (
    K8S_SCENARIO_IDS
    + OS_SCENARIO_IDS
    + CROSS_SCENARIO_IDS
    + BOUNDARY_SCENARIO_IDS
    + PROD_SIM_SCENARIO_IDS
)
NIXOS_REBUILD_RESET_IDS = ("os-1",)


def _scripts_for(
    scenarios_dir: Path, scenario_ids: tuple[str, ...] = ALL_SCENARIO_IDS
) -> list[Path]:
    paths: list[Path] = []
    for sid in scenario_ids:
        paths.append(scenarios_dir / sid / "inject.sh")
        paths.append(scenarios_dir / sid / "reset.sh")
    return paths


@pytest.mark.parametrize("sid", ALL_SCENARIO_IDS)
def test_all_scenarios_have_both_scripts(scenarios_dir: Path, sid: str) -> None:
    assert (scenarios_dir / sid / "inject.sh").is_file()
    assert (scenarios_dir / sid / "reset.sh").is_file()


def test_all_scripts_have_shebang(scenarios_dir: Path) -> None:
    for path in _scripts_for(scenarios_dir, ALL_SCENARIO_IDS):
        first_line = path.read_text().splitlines()[0]
        assert first_line == "#!/usr/bin/env bash", (
            f"{path}: bad shebang {first_line!r}"
        )


def test_all_scripts_have_safety_flags(scenarios_dir: Path) -> None:
    for path in _scripts_for(scenarios_dir, ALL_SCENARIO_IDS):
        head = path.read_text().splitlines()[:10]
        assert "set -euo pipefail" in head, (
            f"{path}: missing `set -euo pipefail` in first 10 lines"
        )


def test_all_scripts_accept_seed_arg(scenarios_dir: Path) -> None:
    for path in _scripts_for(scenarios_dir, ALL_SCENARIO_IDS):
        body = path.read_text()
        assert 'SEED="${1:-1}"' in body, f'{path}: missing SEED="${{1:-1}}" convention'


def test_all_scripts_executable(scenarios_dir: Path) -> None:
    for path in _scripts_for(scenarios_dir, ALL_SCENARIO_IDS):
        mode = path.stat().st_mode
        assert mode & stat.S_IXUSR, f"{path}: user-execute bit not set"


def test_all_reset_scripts_apply_manifests(scenarios_dir: Path) -> None:
    for sid in K8S_SCENARIO_IDS:
        reset_sh = scenarios_dir / sid / "reset.sh"
        assert "apply -f" in reset_sh.read_text(), (
            f"{reset_sh}: missing kubectl apply -f"
        )


def test_all_reset_scripts_resume_flux(scenarios_dir: Path) -> None:
    for sid in K8S_SCENARIO_IDS:
        reset_sh = scenarios_dir / sid / "reset.sh"
        body = reset_sh.read_text()
        assert "resume kustomization flux-system" in body, (
            f"{reset_sh}: missing flux resume recovery step"
        )


@pytest.mark.parametrize("script_name", ["inject.sh", "reset.sh"])
@pytest.mark.parametrize("sid", ALL_SCENARIO_IDS)
def test_all_scripts_syntax_valid(
    scenarios_dir: Path, sid: str, script_name: str
) -> None:
    path = scenarios_dir / sid / script_name
    result = subprocess.run(
        ["bash", "-n", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"{path}: bash -n failed: {result.stderr}"


def test_os_reset_scripts_call_nixos_rebuild(scenarios_dir: Path) -> None:
    """OS and cross reset scripts must call nixos-rebuild switch
    to pin committed generation before next run."""
    for sid in NIXOS_REBUILD_RESET_IDS:
        reset_sh = scenarios_dir / sid / "reset.sh"
        body = reset_sh.read_text()
        assert "nixos-rebuild switch" in body, (
            f"{reset_sh}: missing `nixos-rebuild switch`"
        )


def test_os_reset_scripts_no_kubectl_apply(scenarios_dir: Path) -> None:
    """OS-only scenarios (os-1..3) must not use kubectl apply — pattern differs
    from K8s scenarios (cross-2 is K8s-recovered and so is excluded)."""
    for sid in OS_SCENARIO_IDS:
        reset_sh = scenarios_dir / sid / "reset.sh"
        body = reset_sh.read_text()
        assert "kubectl apply -f" not in body, (
            f"{reset_sh}: OS reset must not call `kubectl apply -f`"
        )


def test_os3_inject_fills_named_path(scenarios_dir: Path) -> None:
    """os-3 must fill a named recovery file under /var/lib/rancher/k3s,
    not the Nix store or root filesystem."""
    inject_sh = scenarios_dir / "os-3" / "inject.sh"
    body = inject_sh.read_text()
    assert "/var/lib/rancher/k3s/eval-fill.img" in body, (
        f"{inject_sh}: os-3 fill path must be /var/lib/rancher/k3s/eval-fill.img"
    )
    assert "/nix" not in body, f"{inject_sh}: must not touch Nix store"


def test_load_scenarios_includes_prod_sim(scenarios_dir: Path) -> None:
    from eval.scenario import load_scenarios

    ids = {s.id for s in load_scenarios(scenarios_dir)}
    for expected in ("pg-1", "redis-1", "ingress-1"):
        assert expected in ids, f"scenario {expected} not found in load_scenarios"


def test_k8s2_inject_uses_app_crash_mode(scenarios_dir: Path) -> None:
    inject_sh = scenarios_dir / "k8s-2" / "inject.sh"
    content = inject_sh.read_text()
    assert "APP_CRASH_MODE" in content
    assert "VIGIL_CRASH" not in content


def test_health_gate_targets_cluster_apps_kustomization() -> None:
    script = Path("eval/scripts/health-gate.sh").read_text()
    non_comment_lines = [
        line for line in script.splitlines() if not line.lstrip().startswith("#")
    ]
    body = "\n".join(non_comment_lines)
    assert "-n flux-system cluster-apps" in body
    assert "-n flux-system flux-system" not in body


def test_health_gate_checks_cluster_infrastructure_precondition() -> None:
    script = Path("eval/scripts/health-gate.sh").read_text()
    assert "check_cluster_infrastructure_ready()" in script
    loop_guard = next(
        (
            line
            for line in script.splitlines()
            if "check_nodes_ready" in line and "check_flux_kustomization_ready" in line
        ),
        None,
    )
    assert loop_guard is not None, "while-loop guard line not found"
    infra_idx = loop_guard.index("check_cluster_infrastructure_ready")
    flux_idx = loop_guard.index("check_flux_kustomization_ready")
    assert infra_idx < flux_idx
