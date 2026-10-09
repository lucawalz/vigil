import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from vigil_lab import cli
from vigil_lab.cli import (
    EXIT_FAILURE,
    EXIT_OK,
    build_parser,
    cmd_up,
    eval_target,
    main,
)
from vigil_lab.proc import LabError
from vigil_lab.state import LabPaths

INHERITED_NIX_CONFIG = "builders = ssh-ng://builder@example.invalid x86_64-linux"
REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("up_args", "match"),
    [
        (["--branch", "eval/odd branch"], "'eval/odd branch'"),
        (["--branch=-lab"], "'-lab'"),
        (["--repo", "vigil"], "'vigil'"),
        (["--repo", "lucawalz/vigil\n"], "not a GitHub OWNER/NAME"),
        (["--repo", "lucawalz/.."], "'lucawalz/..'"),
        (["--repo", "./vigil"], "'./vigil'"),
    ],
)
def test_up_rejects_invalid_settings_before_persisting_them(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    up_args: list[str],
    match: str,
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    monkeypatch.chdir(REPO_ROOT)
    args = build_parser().parse_args(["up", *up_args])
    with pytest.raises(LabError, match=match):
        cmd_up(args)
    assert not LabPaths(tmp_path / "vigil-lab").settings.exists()


def _fake_lab(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, alive: set[str]
) -> list[str]:
    calls: list[str] = []
    hosts = tuple(
        SimpleNamespace(name=name, role=name, index=0, hub_mac="", flake_attrs={})
        for name in ("cp", "w1")
    )
    ctx = SimpleNamespace(
        paths=LabPaths(tmp_path / "vigil-lab"),
        plan=SimpleNamespace(hosts=hosts),
        platform="darwin",
    )
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    monkeypatch.setattr(cli, "_context", lambda paths: ctx)
    monkeypatch.setattr(cli, "_boot", lambda ctx, settings: calls.append("boot"))
    monkeypatch.setattr(
        cli, "pid_alive", lambda pid: pid.stem.removeprefix("vm-") in alive
    )
    monkeypatch.setattr(
        cli,
        "terminate",
        lambda pid: calls.append(f"stop:{pid.stem.removeprefix('vm-')}"),
    )
    monkeypatch.setattr(
        cli.preflight,
        "run_memory_preflight",
        lambda platform: calls.append("memory"),
    )
    monkeypatch.setattr(
        cli.images, "clone_golden", lambda ctx, host: calls.append(f"clone:{host.name}")
    )
    monkeypatch.setattr(
        cli.images, "ensure_golden", lambda ctx, hosts: calls.append("golden")
    )
    monkeypatch.setattr(cli, "save_settings", lambda paths, settings: None)
    monkeypatch.setattr(cli, "ensure_secrets", lambda paths: None)
    monkeypatch.setattr(cli.cluster, "invoking_checkout", lambda: REPO_ROOT)
    monkeypatch.setattr(cli.cluster, "ensure_scratch_clone", lambda *args: None)
    monkeypatch.setattr(cli.cluster, "ensure_branch", lambda *args: None)
    monkeypatch.setattr(cli, "_validate_branch", lambda branch: None)
    monkeypatch.setattr(
        cli, "load_settings", lambda paths: SimpleNamespace(golden=True)
    )
    return calls


def test_reset_checks_memory_after_every_vm_is_terminated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _fake_lab(tmp_path, monkeypatch, {"cp", "w1"})
    cli.cmd_reset(build_parser().parse_args(["reset"]))
    assert calls == ["stop:cp", "stop:w1", "memory", "clone:cp", "clone:w1", "boot"]


@pytest.mark.parametrize(
    ("alive", "checked"), [({"cp", "w1"}, False), ({"cp"}, True), (set(), True)]
)
def test_up_checks_memory_only_when_it_starts_machines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, alive: set[str], checked: bool
) -> None:
    calls = _fake_lab(tmp_path, monkeypatch, alive)
    LabPaths(tmp_path / "vigil-lab").ensure()
    cmd_up(build_parser().parse_args(["up", "--repo", "owner/name"]))
    assert ("memory" in calls) is checked
    if checked:
        assert calls.index("memory") < calls.index("golden")


def test_eval_target_marks_github_runners() -> None:
    assert eval_target({"GITHUB_ACTIONS": "true"}) == "runner"
    assert eval_target({}) == "lab"


def test_main_neutralises_builders_before_any_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    monkeypatch.setenv("NIX_CONFIG", INHERITED_NIX_CONFIG)
    assert main(["agent", "stop"]) == EXIT_OK
    builders = [
        line
        for line in os.environ["NIX_CONFIG"].splitlines()
        if line.startswith("builders ")
    ]
    assert builders[-1] == "builders ="


def test_main_reports_lab_errors_without_a_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    monkeypatch.setenv("NIX_CONFIG", "")
    assert main(["agent", "start"]) == EXIT_FAILURE
    assert "lab up" in capsys.readouterr().err
