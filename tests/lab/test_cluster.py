import os
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
from vigil_lab import cluster
from vigil_lab.addresses import parse_address_plan
from vigil_lab.cluster import (
    CREDENTIAL_HELPER,
    FLUX_SYNC_SCRIPT,
    HELPER_KEY,
    RBAC_DIR,
    apply_scratch_git_config,
    ensure_branch,
    ensure_scratch_clone,
    parse_github_repo,
    worker_setup_command,
)
from vigil_lab.proc import LabError
from vigil_lab.qemu import X86_64_LINUX
from vigil_lab.state import LabContext, LabPaths, LabSettings

REPO = "example/vigil"
ODD_BRANCH = "eval/odd branch"
REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures" / "addresses.json"


def test_cluster_files_resolve_from_the_repository_source() -> None:
    assert (REPO_ROOT / FLUX_SYNC_SCRIPT).is_file()
    assert (REPO_ROOT / RBAC_DIR / "kustomization.yaml").is_file()


def test_bootstrap_runs_flux_sync_from_the_repository_source(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "source"
    ctx = LabContext(
        LabPaths(tmp_path / "state"),
        "linux",
        X86_64_LINUX,
        "kvm",
        "path:/flake?dir=infra/nixos",
        source,
        tmp_path,
        parse_address_plan(FIXTURE.read_text()),
    )
    settings = LabSettings(REPO, "eval/lab", "lab", True, str(tmp_path))
    commands: list[list[str]] = []

    def fake_run(args: Sequence[str], **_: object) -> str:
        commands.append(list(args))
        return ""

    monkeypatch.setattr(cluster, "wait_for_ssh", lambda *_: None)
    monkeypatch.setattr(cluster, "refetch_kubeconfigs", lambda _: None)
    monkeypatch.setattr(cluster, "_apply_generated", lambda *_: None)
    monkeypatch.setattr(cluster, "run", fake_run)
    cluster.bootstrap(ctx, settings)
    assert ["bash", str(source / FLUX_SYNC_SCRIPT)] == commands[-1][:2]


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/example/vigil.git",
        "https://github.com/example/vigil",
        "git@github.com:example/vigil.git",
        "https://github.com/example/vigil/\n",
    ],
)
def test_parse_github_repo_accepts_https_and_ssh_remotes(url: str) -> None:
    assert parse_github_repo(url) == REPO


def test_parse_github_repo_rejects_other_hosts() -> None:
    with pytest.raises(LabError, match="--repo"):
        parse_github_repo("https://gitlab.example.invalid/example/vigil.git")


def test_worker_setup_quotes_the_branch_for_the_remote_shell() -> None:
    command = worker_setup_command(REPO, ODD_BRANCH)
    assert "printf '%s\\n' 'eval/odd branch' > /etc/vigil/branch" in command
    assert command.endswith("ln -sfn /opt/vigil/infra/nixos /opt/nixos-config")


def test_scratch_clone_refuses_state_inside_checkout(tmp_path: Path) -> None:
    checkout = tmp_path / "vigil"
    checkout.mkdir()
    with pytest.raises(LabError, match="inside the checkout"):
        ensure_scratch_clone(LabPaths(checkout / ".state"), REPO, checkout)
    with pytest.raises(LabError, match="inside the checkout"):
        ensure_scratch_clone(LabPaths(tmp_path), REPO, tmp_path / "repo")


def test_scratch_clone_points_an_existing_clone_at_the_requested_repo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    paths = LabPaths(tmp_path)
    (paths.repo / ".git").mkdir(parents=True)
    commands: list[list[str]] = []

    def fake_run(args: Sequence[str], **_: object) -> str:
        commands.append(list(args))
        return ""

    monkeypatch.setattr(cluster, "run", fake_run)
    ensure_scratch_clone(paths, REPO, None)
    set_url = ["git", "-C", str(paths.repo), "remote", "set-url", "origin"]
    assert commands[0] == [*set_url, f"https://github.com/{REPO}.git"]
    assert commands[1][3] == "fetch"


def test_scratch_clone_resets_the_credential_helper_list_before_adding_its_own(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    paths = LabPaths(tmp_path)
    (paths.repo / ".git").mkdir(parents=True)
    commands: list[list[str]] = []

    def fake_run(args: Sequence[str], **_: object) -> str:
        commands.append(list(args))
        return ""

    monkeypatch.setattr(cluster, "run", fake_run)
    ensure_scratch_clone(paths, REPO, None)
    config = ["git", "-C", str(paths.repo), "config"]
    assert [*config, "--replace-all", HELPER_KEY, ""] in commands
    assert [*config, "--add", HELPER_KEY, CREDENTIAL_HELPER] in commands
    assert commands.index([*config, "--replace-all", HELPER_KEY, ""]) < commands.index(
        [*config, "--add", HELPER_KEY, CREDENTIAL_HELPER]
    )


def test_scratch_clone_authenticates_through_the_git_mcp_credential_helper_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_git_mcp = fake_bin / "git-mcp"
    fake_git_mcp.write_text(
        '#!/bin/sh\n[ "$1 $2" = "credential get" ] || exit 0\n'
        'printf "username=x-access-token\\npassword=%s\\n" "$GITHUB_TOKEN"\n'
    )
    fake_git_mcp.chmod(0o755)
    monkeypatch.setenv("PATH", f"{fake_bin}{os.pathsep}{os.environ['PATH']}")
    system_helper = tmp_path / "system-helper"
    system_helper.write_text('#!/bin/sh\nprintf "password=system-helper\\n"\n')
    system_helper.chmod(0o755)
    system_config = tmp_path / "system.gitconfig"
    system_config.write_text(f"[credential]\n\thelper = {system_helper}\n")
    global_config = tmp_path / "global.gitconfig"
    global_config.write_text("")
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(system_config))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_config))
    monkeypatch.setenv("GITHUB_TOKEN", "lab-token")
    repo = tmp_path / "scratch"
    _git("init", "--quiet", str(repo), cwd=tmp_path)
    apply_scratch_git_config(repo)
    apply_scratch_git_config(repo)
    values = subprocess.run(
        ["git", "config", "--local", "--get-all", HELPER_KEY],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert values == f"\n{CREDENTIAL_HELPER}\n"
    filled = subprocess.run(
        ["git", "credential", "fill"],
        cwd=repo,
        input="protocol=https\nhost=github.com\n\n",
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "password=lab-token\n" in filled
    assert "system-helper" not in filled


@pytest.fixture
def clone_of_remote(tmp_path: Path) -> Path:
    remote = tmp_path / "remote.git"
    _git(
        "init", "--quiet", "--bare", "--initial-branch=main", str(remote), cwd=tmp_path
    )
    clone = tmp_path / "clone"
    _git("clone", "--quiet", str(remote), str(clone), cwd=tmp_path)
    _git(
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.invalid",
        "commit",
        "--quiet",
        "--allow-empty",
        "-m",
        "base",
        cwd=clone,
    )
    _git("push", "--quiet", "origin", "main", cwd=clone)
    _git("fetch", "--quiet", "origin", cwd=clone)
    return clone


APP_SETTINGS = {
    "GITHUB_APP_CLIENT_ID": "Iv1.abc",
    "GITHUB_APP_PRIVATE_KEY_FILE": "/keys/app.pem",
}


def test_ensure_branch_needs_credentials_to_create_a_missing_branch(
    clone_of_remote: Path,
) -> None:
    with pytest.raises(LabError, match="GITHUB_APP_CLIENT_ID.*GITHUB_TOKEN"):
        ensure_branch(clone_of_remote, "eval/lab", REPO, {})


def test_ensure_branch_rejects_incomplete_app_settings(
    clone_of_remote: Path,
) -> None:
    with pytest.raises(LabError, match="GITHUB_TOKEN"):
        ensure_branch(
            clone_of_remote,
            "eval/lab",
            REPO,
            {"GITHUB_APP_CLIENT_ID": APP_SETTINGS["GITHUB_APP_CLIENT_ID"]},
        )


@pytest.mark.parametrize("credentials", [{"GITHUB_TOKEN": "t"}, APP_SETTINGS])
def test_ensure_branch_creates_a_missing_branch_from_main(
    clone_of_remote: Path, credentials: dict[str, str]
) -> None:
    ensure_branch(clone_of_remote, "eval/lab", REPO, credentials)
    assert _git("ls-remote", "--heads", "origin", "eval/lab", cwd=clone_of_remote)
    ensure_branch(clone_of_remote, "eval/lab", REPO, {})


def test_ensure_branch_gives_the_credential_helper_the_repository_url(
    monkeypatch: pytest.MonkeyPatch, clone_of_remote: Path
) -> None:
    pushes: list[Mapping[str, str] | None] = []

    def fake_run(args: Sequence[str], **kwargs: Any) -> str:
        pushes.append(kwargs.get("env"))
        return ""

    monkeypatch.setattr(cluster, "run", fake_run)
    ensure_branch(clone_of_remote, "eval/lab", REPO, {"GITHUB_TOKEN": "t"})
    assert pushes == [
        {"GITHUB_TOKEN": "t", "REPO_URL": f"https://github.com/{REPO}.git"}
    ]
