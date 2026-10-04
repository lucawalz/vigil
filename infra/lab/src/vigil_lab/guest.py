from __future__ import annotations

from vigil_lab.addresses import LabHost
from vigil_lab.proc import SSH_PROBE_TIMEOUT_S, probe, wait_until
from vigil_lab.qemu import LOOPBACK
from vigil_lab.state import LabPaths

GUEST_USER = "root"
CONNECT_TIMEOUT_S = 10
SSH_OPTIONS = (
    "UserKnownHostsFile=/dev/null",
    "StrictHostKeyChecking=no",
    "IdentitiesOnly=yes",
    "LogLevel=ERROR",
    f"ConnectTimeout={CONNECT_TIMEOUT_S}",
)


def guest_ssh_args(paths: LabPaths, host: LabHost, command: str) -> list[str]:
    args = [
        "ssh",
        "-F",
        "/dev/null",
        "-i",
        str(paths.lab_key),
        "-p",
        str(host.ssh_port),
    ]
    for option in SSH_OPTIONS:
        args += ["-o", option]
    return [*args, f"{GUEST_USER}@{LOOPBACK}", command]


def ssh_ok(paths: LabPaths, host: LabHost, command: str = "true") -> bool:
    return probe(guest_ssh_args(paths, host, command), SSH_PROBE_TIMEOUT_S)


def wait_for_ssh(paths: LabPaths, host: LabHost, timeout_s: float) -> None:
    wait_until(lambda: ssh_ok(paths, host), timeout_s, f"ssh on {host.name}")
