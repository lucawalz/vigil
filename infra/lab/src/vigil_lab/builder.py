from __future__ import annotations

import base64
import contextlib
import os
import shutil
import stat
from collections.abc import Iterator
from pathlib import Path

from vigil_lab.preflight import DARWIN
from vigil_lab.proc import (
    SSH_PROBE_TIMEOUT_S,
    LabError,
    pid_alive,
    probe,
    run,
    spawn,
    terminate,
    wait_until,
)
from vigil_lab.qemu import BUILDER, exclusive_start
from vigil_lab.state import LabContext, LabPaths

BUILDER_USER = "builder"
BUILDER_SYSTEM = "aarch64-linux"
BUILDER_SSH_PORT = 31022
BUILDER_MAX_JOBS = 4
BUILDER_SPEED_FACTOR = 1
BUILDER_FEATURES = "kvm,benchmark,big-parallel"
BUILDER_SMP = 4
BUILDER_READY_TIMEOUT_S = 300.0
BUILDER_POWEROFF_TIMEOUT_S = 30.0
BUILDER_KEY_NAME = "builder_ed25519"
RUN_BUILDER_INSTALLABLE = "nixpkgs#darwin.linux-builder.passthru.run-builder"
NIXPKGS_PATH_INSTALLABLE = "nixpkgs#path"
BUILDER_HOST_KEY = Path("nixos/modules/profiles/keys/ssh_host_ed25519_key.pub")


def with_builders(config: str, builders: str) -> str:
    lines = [line for line in config.splitlines() if line.strip()]
    lines.append(f"builders = {builders}".rstrip())
    if builders:
        lines.append("builders-use-substitutes = true")
    return "\n".join(lines) + "\n"


def _builder_keys(paths: LabPaths) -> Path:
    return paths.keys / BUILDER_USER


def _builder_ssh(key: Path, command: str) -> list[str]:
    return [
        "ssh",
        "-F",
        "/dev/null",
        "-i",
        str(key),
        "-p",
        str(BUILDER_SSH_PORT),
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        "LogLevel=ERROR",
        f"{BUILDER_USER}@localhost",
        command,
    ]


def _clear_certs(tmp: Path) -> None:
    certs = tmp / "certs"
    if certs.exists():
        for path in [certs, *certs.rglob("*")]:
            path.chmod(path.stat().st_mode | stat.S_IWUSR)
        shutil.rmtree(certs)


def start(paths: LabPaths, flake: str) -> str:
    exclusive_start(paths, BUILDER)
    keys = _builder_keys(paths)
    keys.mkdir(exist_ok=True)
    key = keys / BUILDER_KEY_NAME
    if not key.exists():
        run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)])
    workdir = paths.root / BUILDER
    runner = workdir / "runner"
    run(
        [
            "nix",
            "build",
            "--inputs-from",
            flake,
            "--out-link",
            str(runner),
            RUN_BUILDER_INSTALLABLE,
        ],
        log_file=paths.log("builder-build"),
    )
    nixpkgs = Path(
        run(["nix", "eval", "--raw", "--inputs-from", flake, NIXPKGS_PATH_INSTALLABLE])
    )
    tmp = workdir / "tmp"
    _clear_certs(tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    exclusive_start(paths, BUILDER)
    env = {
        **os.environ,
        "KEYS": str(keys),
        "TMPDIR": str(tmp),
        "USE_TMPDIR": "1",
        "QEMU_OPTS": f"-smp {BUILDER_SMP}",
    }
    spawn(
        [str(runner / "bin" / "run-builder")],
        pid_file=paths.pid(BUILDER),
        log_file=paths.log(BUILDER),
        cwd=workdir,
        env=env,
    )
    wait_until(
        lambda: probe(_builder_ssh(key, "true"), SSH_PROBE_TIMEOUT_S),
        BUILDER_READY_TIMEOUT_S,
        "the image builder to accept ssh",
    )
    host_key = (nixpkgs / BUILDER_HOST_KEY).read_bytes()
    return " ".join(
        [
            f"ssh-ng://{BUILDER_USER}@localhost:{BUILDER_SSH_PORT}",
            BUILDER_SYSTEM,
            str(key),
            str(BUILDER_MAX_JOBS),
            str(BUILDER_SPEED_FACTOR),
            BUILDER_FEATURES,
            "-",
            base64.b64encode(host_key).decode(),
        ]
    )


def stop(paths: LabPaths) -> None:
    if pid_alive(paths.pid(BUILDER)):
        probe(
            _builder_ssh(
                _builder_keys(paths) / BUILDER_KEY_NAME, "sudo systemctl poweroff"
            ),
            SSH_PROBE_TIMEOUT_S,
        )
        with contextlib.suppress(LabError):
            wait_until(
                lambda: not pid_alive(paths.pid(BUILDER)),
                BUILDER_POWEROFF_TIMEOUT_S,
                "the image builder to power off",
            )
    terminate(paths.pid(BUILDER))


@contextlib.contextmanager
def build_env(ctx: LabContext) -> Iterator[dict[str, str]]:
    if ctx.platform != DARWIN:
        yield dict(os.environ)
        return
    try:
        line = start(ctx.paths, ctx.flake)
        yield {
            **os.environ,
            "NIX_CONFIG": with_builders(os.environ.get("NIX_CONFIG", ""), line),
        }
    finally:
        stop(ctx.paths)
