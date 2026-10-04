import subprocess
from pathlib import Path

import pytest
from vigil_lab.cluster import (
    ensure_branch,
    ensure_scratch_clone,
    parse_github_repo,
    worker_setup_command,
)
from vigil_lab.proc import LabError
from vigil_lab.state import LabPaths

REPO = "example/vigil"
ODD_BRANCH = "eval/odd branch"


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


def test_ensure_branch_needs_a_token_to_create_a_missing_branch(
    clone_of_remote: Path,
) -> None:
    with pytest.raises(LabError, match="GITHUB_TOKEN"):
        ensure_branch(clone_of_remote, "eval/lab", {})


def test_ensure_branch_creates_a_missing_branch_from_main(
    clone_of_remote: Path,
) -> None:
    ensure_branch(clone_of_remote, "eval/lab", {"GITHUB_TOKEN": "t"})
    assert _git("ls-remote", "--heads", "origin", "eval/lab", cwd=clone_of_remote)
    ensure_branch(clone_of_remote, "eval/lab", {})
