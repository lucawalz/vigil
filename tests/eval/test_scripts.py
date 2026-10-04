"""Static validation for the eval health-gate and reset scripts."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

NIXOS_REBUILD_RESET_IDS = ("os-1",)
REPO = Path(__file__).resolve().parents[2]
SHARED_BRANCH = "chore/eval-cluster-baseline"
CELL_BRANCH = "eval/123/k8s-1"
APP_MANIFEST = Path(
    "infra/overlays/hetzner/kubernetes/clusters/hetzner/apps/vigil-app.yaml"
)
EXECUTABLE = 0o755


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


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _stub(bin_dir: Path, name: str, body: str = "exit 0") -> None:
    stub = bin_dir / name
    stub.write_text(f"#!/bin/sh\n{body}\n")
    stub.chmod(EXECUTABLE)


@pytest.fixture
def eval_repo(tmp_path: Path) -> dict[str, Path]:
    remote = tmp_path / "remote.git"
    _git(
        "init", "--quiet", "--bare", "--initial-branch=main", str(remote), cwd=tmp_path
    )
    clone = tmp_path / "clone"
    _git("clone", "--quiet", str(remote), str(clone), cwd=tmp_path)
    _git("config", "user.name", "eval-harness", cwd=clone)
    _git("config", "user.email", "eval@vigil.local", cwd=clone)
    manifest = clone / APP_MANIFEST
    manifest.parent.mkdir(parents=True)
    manifest.write_text((REPO / APP_MANIFEST).read_text())
    scripts = clone / "eval" / "scripts"
    scripts.mkdir(parents=True)
    for script in (REPO / "eval" / "scripts").glob("*.sh"):
        (scripts / script.name).write_text(script.read_text())
        (scripts / script.name).chmod(EXECUTABLE)
    _git("add", "-A", cwd=clone)
    _git("commit", "--quiet", "-m", "baseline", cwd=clone)
    _git("push", "--quiet", "origin", "main", cwd=clone)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in ("flux", "ssh", "curl"):
        _stub(bin_dir, name)
    _stub(bin_dir, "kubectl", "echo True")
    return {"remote": remote, "clone": clone, "bin": bin_dir, "tmp": tmp_path}


def _env(repo: dict[str, Path], **extra: str) -> dict[str, str]:
    env = {
        key: value for key, value in os.environ.items() if key != "VIGIL_EVAL_BRANCH"
    }
    env.update(
        PATH=f"{repo['bin']}{os.pathsep}{os.environ['PATH']}",
        VIGIL_REPO_ROOT=str(repo["clone"]),
        EVAL_RUNNER_KUBECONFIG=str(repo["tmp"] / "kubeconfig"),
        FAULT_INJECTION_KUBECONFIG=str(repo["tmp"] / "kubeconfig"),
        SSH_KEY_PATH=str(repo["tmp"] / "key"),
    )
    env.update(extra)
    return env


def _remote_sha(repo: dict[str, Path], branch: str) -> str:
    return _git("rev-parse", f"refs/heads/{branch}", cwd=repo["remote"])


def test_reset_eval_baseline_pushes_main_to_the_configured_branch(
    eval_repo: dict[str, Path],
) -> None:
    subprocess.run(
        ["bash", str(REPO / "eval/scripts/reset-eval-baseline.sh")],
        env=_env(eval_repo, VIGIL_EVAL_BRANCH=CELL_BRANCH),
        check=True,
        capture_output=True,
    )
    assert _remote_sha(eval_repo, CELL_BRANCH) == _remote_sha(eval_repo, "main")


def test_reset_eval_baseline_defaults_to_the_shared_branch(
    eval_repo: dict[str, Path],
) -> None:
    subprocess.run(
        ["bash", str(REPO / "eval/scripts/reset-eval-baseline.sh")],
        env=_env(eval_repo),
        check=True,
        capture_output=True,
    )
    assert _remote_sha(eval_repo, SHARED_BRANCH) == _remote_sha(eval_repo, "main")


def test_k8s_1g_inject_commits_to_the_configured_branch_without_backup_files(
    eval_repo: dict[str, Path],
) -> None:
    subprocess.run(
        ["bash", str(REPO / "eval/scenarios/k8s-1g/inject.sh"), "1"],
        env=_env(eval_repo, VIGIL_EVAL_BRANCH=CELL_BRANCH),
        check=True,
        capture_output=True,
    )
    pushed = _git("show", f"{CELL_BRANCH}:{APP_MANIFEST}", cwd=eval_repo["remote"])
    assert "image: nginx:bad-tag-v9" in pushed
    assert not list(eval_repo["clone"].rglob("*.bak"))


def test_between_scenarios_runs_the_configured_restart_command(
    eval_repo: dict[str, Path],
) -> None:
    marker = eval_repo["tmp"] / "restarted"
    result = subprocess.run(
        ["bash", str(REPO / "eval/scripts/between-scenarios.sh"), "k8s-1g", "k8s"],
        env=_env(
            eval_repo,
            VIGIL_EVAL_BRANCH=CELL_BRANCH,
            PREV_RUN_ID="k8s-1g_1_m_abc1234",
            VIGIL_ORCHESTRATOR_RESTART_CMD=f"touch {marker}",
        ),
        check=True,
        capture_output=True,
        text=True,
    )
    assert marker.exists()
    assert "HEALTH_GATE: ok" in result.stdout
    assert f"reset {CELL_BRANCH} to origin/main" in result.stderr


def test_os_scripts_rebuild_the_configured_flake_attribute(scenarios_dir: Path) -> None:
    for script in (
        "os-1/inject.sh",
        "os-1/reset.sh",
        "os-stale-generation/inject.sh",
        "os-stale-generation/reset.sh",
    ):
        body = (scenarios_dir / script).read_text()
        assert "/opt/nixos-config#\\$(cat /etc/vigil/flake-attr)" in body, script
        assert "hetzner-" not in body, script
