import subprocess
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from vigil_lab import builder
from vigil_lab.builder import with_builders
from vigil_lab.proc import LabError, spawn
from vigil_lab.qemu import BUILDER
from vigil_lab.state import LabPaths

INHERITED_BUILDERS = "builders = ssh-ng://builder@example.invalid x86_64-linux"
UNRELATED_SETTING = "max-jobs = 4"
LOCAL_BUILDER = "ssh-ng://builder@localhost:31022 aarch64-linux"
SLEEP_SECONDS = "30"
VM_NAME = "vigil-worker-1"


def _builders_lines(config: str) -> list[str]:
    return [line for line in config.splitlines() if line.startswith("builders ")]


def test_with_builders_overrides_inherited_builders() -> None:
    config = with_builders(f"{INHERITED_BUILDERS}\n{UNRELATED_SETTING}", "")
    assert _builders_lines(config)[-1] == "builders ="
    assert UNRELATED_SETTING in config
    assert "builders-use-substitutes" not in config


def test_local_builder_line_lands_after_the_neutralised_line() -> None:
    config = with_builders(with_builders(INHERITED_BUILDERS, ""), LOCAL_BUILDER)
    assert _builders_lines(config)[-1] == f"builders = {LOCAL_BUILDER}"
    assert config.splitlines()[-1] == "builders-use-substitutes = true"


@pytest.fixture
def sleepers() -> Iterator[list[subprocess.Popen[bytes]]]:
    processes: list[subprocess.Popen[bytes]] = []
    yield processes
    for process in processes:
        process.kill()
        process.wait()


def test_start_refuses_a_second_builder(
    tmp_path: Path, sleepers: list[subprocess.Popen[bytes]]
) -> None:
    paths = LabPaths(tmp_path)
    paths.ensure()
    sleepers.append(
        spawn(
            ["sleep", SLEEP_SECONDS],
            pid_file=paths.pid(BUILDER),
            log_file=paths.log("sleeper"),
        )
    )
    with pytest.raises(LabError, match="already running"):
        builder.start(paths, "flake")


def test_start_rechecks_the_guard_right_before_spawning(
    tmp_path: Path,
    sleepers: list[subprocess.Popen[bytes]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = LabPaths(tmp_path)
    paths.ensure()

    def fake_run(args: Sequence[str], **_: object) -> str:
        if args[:2] == ["nix", "build"]:
            sleepers.append(
                spawn(
                    ["sleep", SLEEP_SECONDS],
                    pid_file=paths.vm_pid(VM_NAME),
                    log_file=paths.log("sleeper"),
                )
            )
        return str(tmp_path)

    def forbidden_spawn(*_: object, **__: object) -> None:
        raise AssertionError("the builder must not spawn while a VM runs")

    monkeypatch.setattr(builder, "run", fake_run)
    monkeypatch.setattr(builder, "spawn", forbidden_spawn)
    with pytest.raises(LabError, match="lab down"):
        builder.start(paths, "flake")
