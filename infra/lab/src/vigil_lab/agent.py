from __future__ import annotations

import os
import shlex
import urllib.error
import urllib.request
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from vigil_lab.addresses import AddressPlan, LabHost
from vigil_lab.cluster import (
    EVAL_RUNNER,
    FAULT_INJECTION,
    GITHUB_URL,
    ORCHESTRATOR_PORT,
    ORCHESTRATOR_URL,
)
from vigil_lab.guest import GUEST_USER, SSH_OPTIONS
from vigil_lab.proc import LabError, pid_alive, spawn, terminate, wait_until
from vigil_lab.qemu import LOOPBACK
from vigil_lab.state import LabPaths, LabSettings, write_private

AGENT = "agent"
HEALTHZ_TIMEOUT_S = 180.0
HEALTHZ_PROBE_TIMEOUT_S = 5.0
LOG_TAIL_LINES = 20
HTTP_OK = 200
EXECUTABLE_MODE = 0o755
PASSTHROUGH_PREFIXES = ("OLLAMA_", "LLM_", "ANTHROPIC_")
PASSTHROUGH_KEYS = frozenset(
    {
        "GITHUB_TOKEN",
        "DIAGNOSIS_TIMEOUT_S",
        "REMEDIATION_TIMEOUT_S",
        "ORCHESTRATOR_RUN_TIMEOUT_S",
    }
)
ORCHESTRATOR_COMMAND = (
    "uv",
    "run",
    "--frozen",
    "--package",
    "vigil-orchestrator",
    "uvicorn",
    "orchestrator.main:app",
    "--host",
    LOOPBACK,
    "--port",
    str(ORCHESTRATOR_PORT),
)


def _path_with_bin_first(bin_dir: Path, current: str) -> str:
    if current.split(os.pathsep)[0] == str(bin_dir):
        return current
    return f"{bin_dir}{os.pathsep}{current}"


def lab_env(
    paths: LabPaths,
    plan: AddressPlan,
    settings: LabSettings,
    *,
    webhook_secret: str,
    lab_command: str,
    environ: Mapping[str, str],
) -> dict[str, str]:
    env = {
        "SSH_HOSTS": ",".join(f"{host.name}:{host.ssh_port}" for host in plan.workers),
        "SSH_USER": GUEST_USER,
        "SSH_KEY_PATH": str(paths.lab_key),
        "EVAL_RUNNER_KUBECONFIG": str(paths.kubeconfig(EVAL_RUNNER)),
        "FAULT_INJECTION_KUBECONFIG": str(paths.kubeconfig(FAULT_INJECTION)),
        "KUBECONFIG": str(paths.kubeconfig(EVAL_RUNNER)),
        "VIGIL_REPO_ROOT": str(paths.repo),
        "VIGIL_EVAL_BRANCH": settings.branch,
        "VIGIL_ORCHESTRATOR_URL": ORCHESTRATOR_URL,
        "VIGIL_ORCHESTRATOR_RESTART_CMD": f"{lab_command} agent restart",
        "VIGIL_BLOCK_ALERT_TRIGGERS": "true",
        "PROM_POLLER_ENABLED": "false",
        "VIGIL_EVAL_TARGET": settings.target,
        "REPO_URL": f"{GITHUB_URL}/{settings.repo}.git",
        "VIGIL_WEBHOOK_SECRET": webhook_secret,
        "EVAL_RUNS_DIR": str(paths.root / "runs"),
        "VIGIL_SCENARIOS_DIR": str(Path(settings.checkout) / "eval" / "scenarios"),
        "PATH": _path_with_bin_first(paths.bin, environ.get("PATH", "")),
    }
    env.update(
        {
            key: value
            for key, value in environ.items()
            if key in PASSTHROUGH_KEYS or key.startswith(PASSTHROUGH_PREFIXES)
        }
    )
    return env


def write_lab_env(path: Path, env: Mapping[str, str]) -> None:
    write_private(
        path, "".join(f"{key}={shlex.quote(value)}\n" for key, value in env.items())
    )


def write_ssh_tools(paths: LabPaths, hosts: Iterable[LabHost], ssh_binary: str) -> None:
    config = paths.root / "ssh_config"
    blocks = [
        f"Host {host.name}\n  HostName {LOOPBACK}\n  Port {host.ssh_port}\n"
        for host in hosts
    ]
    options = "".join(f"  {option.replace('=', ' ', 1)}\n" for option in SSH_OPTIONS)
    blocks.append(
        f"Host *\n  User {GUEST_USER}\n  IdentityFile {paths.lab_key}\n{options}"
    )
    config.write_text("\n".join(blocks))
    wrapper = paths.bin / "ssh"
    ssh = shlex.quote(ssh_binary)
    wrapper.write_text(f'#!/bin/sh\nexec {ssh} -F {shlex.quote(str(config))} "$@"\n')
    wrapper.chmod(EXECUTABLE_MODE)


def _healthy() -> bool:
    try:
        with urllib.request.urlopen(
            f"{ORCHESTRATOR_URL}/healthz", timeout=HEALTHZ_PROBE_TIMEOUT_S
        ) as response:
            return response.status == HTTP_OK
    except (urllib.error.URLError, OSError):
        return False


def start(
    paths: LabPaths,
    plan: AddressPlan,
    settings: LabSettings,
    *,
    lab_command: str,
    ssh_binary: str,
    environ: Mapping[str, str],
    command: Sequence[str] = ORCHESTRATOR_COMMAND,
) -> None:
    write_ssh_tools(paths, plan.hosts, ssh_binary)
    (paths.root / "runs").mkdir(exist_ok=True)
    env = lab_env(
        paths,
        plan,
        settings,
        webhook_secret=paths.webhook_secret.read_text().strip(),
        lab_command=lab_command,
        environ=environ,
    )
    write_lab_env(paths.root / "lab.env", env)
    if not pid_alive(paths.pid(AGENT)):
        spawn(
            command,
            pid_file=paths.pid(AGENT),
            log_file=paths.log(AGENT),
            cwd=Path(settings.checkout),
            env={**environ, **env},
        )
    pid_file = paths.pid(AGENT)
    wait_until(
        lambda: _healthy() or not pid_alive(pid_file),
        HEALTHZ_TIMEOUT_S,
        "the orchestrator /healthz",
    )
    if not pid_alive(pid_file):
        log = paths.log(AGENT)
        tail = log.read_text(errors="replace").splitlines()[-LOG_TAIL_LINES:]
        raise LabError(
            f"the orchestrator exited while starting, see {log}:\n" + "\n".join(tail)
        )


def stop(paths: LabPaths) -> None:
    terminate(paths.pid(AGENT))
