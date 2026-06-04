"""Static validation for the eval health-gate and reset scripts."""

from __future__ import annotations

from pathlib import Path

NIXOS_REBUILD_RESET_IDS = ("os-1",)


def test_os_reset_scripts_call_nixos_rebuild(scenarios_dir: Path) -> None:
    """Reset must pin the committed NixOS generation before the next run."""
    for sid in NIXOS_REBUILD_RESET_IDS:
        reset_sh = scenarios_dir / sid / "reset.sh"
        body = reset_sh.read_text()
        assert "nixos-rebuild switch" in body, (
            f"{reset_sh}: missing `nixos-rebuild switch`"
        )


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
    assert "check_cluster_infrastructure_ready" in script
    assert "check_nodes_ready" in script
    assert "check_flux_kustomization_ready" in script
    infra_idx = script.index("check_cluster_infrastructure_ready")
    flux_idx = script.index("check_flux_kustomization_ready")
    assert infra_idx < flux_idx
