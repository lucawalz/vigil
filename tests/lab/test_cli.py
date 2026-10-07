import os
from pathlib import Path

import pytest
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
