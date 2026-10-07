from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from vigil_lab import agent, builder, cluster, hub, images, preflight, qemu
from vigil_lab.addresses import load_address_plan
from vigil_lab.proc import LabError, pid_alive, run, spawn, terminate, wait_until
from vigil_lab.state import (
    LabContext,
    LabPaths,
    LabSettings,
    default_root,
    ensure_secrets,
    load_settings,
    save_settings,
)

DEFAULT_LAB_BRANCH = "eval/lab"
GITHUB_REPO_NAME_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
DOT_SEGMENTS = frozenset({".", ".."})
LAB_TARGET = "lab"
RUNNER_TARGET = "runner"
HUB = "hub"
HUB_READY_TIMEOUT_S = 10.0
HUB_POLL_INTERVAL_S = 0.1
FLAKE_ENV = "VIGIL_LAB_FLAKE"
SOURCE_ENV = "VIGIL_LAB_SOURCE"
COMMAND_ENV = "VIGIL_LAB_COMMAND"
SSH_ENV = "VIGIL_LAB_SSH"
FIRMWARE_ENV = "VIGIL_LAB_FIRMWARE"
EXIT_OK = 0
EXIT_FAILURE = 1


def eval_target(environ: Mapping[str, str]) -> str:
    return RUNNER_TARGET if environ.get("GITHUB_ACTIONS") == "true" else LAB_TARGET


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise LabError(
            f"{name} is not set; run the lab with `nix run ./infra/nixos#lab -- ...`"
        )
    return value


def _validate_branch(branch: str) -> None:
    try:
        run(["git", "check-ref-format", "--branch", branch])
    except LabError:
        raise LabError(
            f"--branch {branch!r} is not a valid branch name "
            "(see `git check-ref-format --branch`)"
        ) from None


def _validate_repo(repo: str) -> None:
    if not GITHUB_REPO_NAME_RE.fullmatch(repo) or DOT_SEGMENTS & set(repo.split("/")):
        raise LabError(
            f"--repo {repo!r} is not a GitHub OWNER/NAME of letters, digits, "
            "'_', '.' and '-'"
        )


def _context(paths: LabPaths) -> LabContext:
    flake = _required_env(FLAKE_ENV)
    return LabContext(
        paths=paths,
        platform=sys.platform,
        system=preflight.guest_system(sys.platform, os.uname().machine),
        accel=preflight.run_preflight(sys.platform),
        flake=flake,
        source=Path(_required_env(SOURCE_ENV)),
        firmware_dir=Path(_required_env(FIRMWARE_ENV)),
        plan=load_address_plan(flake),
    )


def _start_hub(paths: LabPaths) -> None:
    if pid_alive(paths.pid(HUB)):
        return
    paths.hub_socket.unlink(missing_ok=True)
    spawn(
        [sys.executable, "-m", "vigil_lab", HUB, str(paths.hub_socket)],
        pid_file=paths.pid(HUB),
        log_file=paths.log(HUB),
    )
    wait_until(
        paths.hub_socket.exists,
        HUB_READY_TIMEOUT_S,
        "the hub socket",
        HUB_POLL_INTERVAL_S,
    )


def _boot(ctx: LabContext, settings: LabSettings) -> None:
    _start_hub(ctx.paths)
    for host in ctx.plan.hosts:
        if not pid_alive(ctx.paths.vm_pid(host.name)):
            qemu.start(ctx, host)
    cluster.bootstrap(ctx, settings)


def cmd_up(args: argparse.Namespace) -> None:
    _validate_branch(args.branch)
    checkout = cluster.invoking_checkout()
    if checkout is None or not (checkout / "eval" / "scenarios").is_dir():
        raise LabError("run `lab up` from a vigil checkout")
    repo = args.repo or cluster.parse_github_repo(
        run(["git", "-C", str(checkout), "remote", "get-url", "origin"])
    )
    _validate_repo(repo)
    paths = LabPaths(default_root())
    paths.ensure()
    ctx = _context(paths)
    settings = LabSettings(
        repo=repo,
        branch=args.branch,
        target=eval_target(os.environ),
        golden=not args.no_golden,
        checkout=str(checkout),
    )
    save_settings(paths, settings)
    ensure_secrets(paths)
    cluster.ensure_scratch_clone(paths, repo, checkout)
    cluster.ensure_branch(paths.repo, settings.branch, os.environ)
    hosts = list(ctx.plan.hosts)
    if settings.golden:
        images.ensure_golden(ctx, hosts)
    missing = [
        host
        for host in hosts
        if not pid_alive(paths.vm_pid(host.name)) and not paths.disk(host.name).exists()
    ]
    if settings.golden:
        for host in missing:
            images.clone_golden(ctx, host)
    elif missing:
        images.install_in_place(ctx, missing)
    _boot(ctx, settings)


def cmd_reset(args: argparse.Namespace) -> None:
    paths = LabPaths(default_root())
    settings = load_settings(paths)
    if not settings.golden:
        raise LabError(
            "this lab runs without golden disks; use `lab destroy` and `lab up` instead"
        )
    ctx = _context(paths)
    for host in ctx.plan.hosts:
        terminate(paths.vm_pid(host.name))
        images.clone_golden(ctx, host)
    _boot(ctx, settings)


def cmd_down(args: argparse.Namespace) -> None:
    paths = LabPaths(default_root())
    agent.stop(paths)
    for name in qemu.vm_names(paths):
        qemu.shutdown(paths, name)
    terminate(paths.pid(HUB))
    builder.stop(paths)


def cmd_destroy(args: argparse.Namespace) -> None:
    paths = LabPaths(default_root())
    if paths.root.exists():
        cmd_down(args)
        shutil.rmtree(paths.root)


def cmd_agent(args: argparse.Namespace) -> None:
    paths = LabPaths(default_root())
    if args.action in ("stop", "restart"):
        agent.stop(paths)
    if args.action == "stop":
        return
    settings = load_settings(paths)
    agent.start(
        paths,
        load_address_plan(_required_env(FLAKE_ENV)),
        settings,
        lab_command=_required_env(COMMAND_ENV),
        ssh_binary=_required_env(SSH_ENV),
        environ=os.environ,
    )


def cmd_hub(args: argparse.Namespace) -> None:
    hub.main(Path(args.socket))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lab", description="Local VM lab for the vigil hosts."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    up = commands.add_parser(
        "up", help="build or reuse the disks, boot the VMs and bootstrap the cluster"
    )
    up.add_argument(
        "--no-golden",
        action="store_true",
        help="install the disks in place without golden copies",
    )
    up.add_argument(
        "--repo",
        help="GitHub owner/name the guests and Flux track (default: the origin remote)",
    )
    up.add_argument(
        "--branch",
        default=DEFAULT_LAB_BRANCH,
        help=f"branch the guests and Flux track (default: {DEFAULT_LAB_BRANCH})",
    )
    up.set_defaults(handler=cmd_up)
    for name, handler, text in (
        ("down", cmd_down, "stop every lab process and keep the state"),
        ("reset", cmd_reset, "return the VMs to a fresh cluster from the golden disks"),
        (
            "destroy",
            cmd_destroy,
            "stop every lab process and delete the state directory",
        ),
    ):
        commands.add_parser(name, help=text).set_defaults(handler=handler)
    agent_parser = commands.add_parser(
        "agent", help="run the orchestrator and the MCP servers natively"
    )
    agent_parser.add_argument("action", choices=("start", "stop", "restart"))
    agent_parser.set_defaults(handler=cmd_agent)
    hub_parser = commands.add_parser(
        HUB, help="serve the VM hub on a Unix socket (started by up)"
    )
    hub_parser.add_argument("socket")
    hub_parser.set_defaults(handler=cmd_hub)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    os.environ["NIX_CONFIG"] = builder.with_builders(
        os.environ.get("NIX_CONFIG", ""), ""
    )
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except LabError as exc:
        print(f"lab: {exc}", file=sys.stderr)
        return EXIT_FAILURE
    return EXIT_OK
