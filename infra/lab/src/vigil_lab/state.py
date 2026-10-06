from __future__ import annotations

import json
import os
import secrets
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path

from vigil_lab.addresses import AddressPlan
from vigil_lab.proc import LabError, run

STATE_DIR_NAME = "vigil-lab"
PRIVATE_DIR_MODE = 0o700
PRIVATE_FILE_MODE = 0o600
MAX_UNIX_SOCKET_PATH_BYTES = 103
SECRET_BYTES = 32
LAB_KEY_COMMENT = "vigil-lab"


def default_root(environ: Mapping[str, str] = os.environ) -> Path:
    base = environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / STATE_DIR_NAME


def write_private(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, PRIVATE_FILE_MODE)
    with os.fdopen(fd, "w") as handle:
        handle.write(text)
    path.chmod(PRIVATE_FILE_MODE)


@dataclass(frozen=True)
class LabPaths:
    root: Path

    @property
    def keys(self) -> Path:
        return self.root / "keys"

    @property
    def golden(self) -> Path:
        return self.root / "golden"

    @property
    def run(self) -> Path:
        return self.root / "run"

    @property
    def repo(self) -> Path:
        return self.root / "repo"

    @property
    def bin(self) -> Path:
        return self.root / "bin"

    @property
    def settings(self) -> Path:
        return self.root / "settings.json"

    @property
    def lab_key(self) -> Path:
        return self.keys / "lab_ed25519"

    @property
    def k3s_token(self) -> Path:
        return self.keys / "k3s-token"

    @property
    def webhook_secret(self) -> Path:
        return self.keys / "webhook-secret"

    @property
    def hub_socket(self) -> Path:
        return self._socket("hub.sock")

    def disk(self, host: str) -> Path:
        return self.run / f"{host}.qcow2"

    def vars(self, host: str) -> Path:
        return self.run / f"{host}-vars.fd"

    def golden_disk(self, host: str) -> Path:
        return self.golden / f"{host}.qcow2"

    def golden_meta(self, host: str) -> Path:
        return self.golden / f"{host}.json"

    def serial(self, host: str) -> Path:
        return self._socket(f"{host}.serial")

    def serial_log(self, host: str) -> Path:
        return self.log(f"{host}-serial")

    def monitor(self, host: str) -> Path:
        return self._socket(f"{host}.monitor")

    def pid(self, name: str) -> Path:
        return self.run / f"{name}.pid"

    def vm_pid(self, host: str) -> Path:
        return self.pid(f"vm-{host}")

    def kubeconfig(self, name: str) -> Path:
        return self.root / "kube" / f"{name}.yaml"

    def log(self, name: str) -> Path:
        return self.root / "logs" / f"{name}.log"

    def ensure(self) -> None:
        self.root.mkdir(mode=PRIVATE_DIR_MODE, parents=True, exist_ok=True)
        self.root.chmod(PRIVATE_DIR_MODE)
        for directory in (
            self.keys,
            self.golden,
            self.run,
            self.bin,
            self.root / "kube",
            self.root / "logs",
        ):
            directory.mkdir(exist_ok=True)

    def _socket(self, name: str) -> Path:
        path = self.run / name
        if len(os.fsencode(path)) > MAX_UNIX_SOCKET_PATH_BYTES:
            raise LabError(
                f"socket path {path} exceeds {MAX_UNIX_SOCKET_PATH_BYTES} bytes; "
                "set XDG_STATE_HOME to a shorter directory"
            )
        return path


@dataclass(frozen=True)
class LabSettings:
    repo: str
    branch: str
    target: str
    golden: bool
    checkout: str


def save_settings(paths: LabPaths, settings: LabSettings) -> None:
    write_private(paths.settings, json.dumps(asdict(settings), indent=2))


def load_settings(paths: LabPaths) -> LabSettings:
    try:
        data = json.loads(paths.settings.read_text())
    except FileNotFoundError:
        raise LabError(f"no lab at {paths.root}; run `lab up` first") from None
    return LabSettings(**data)


def ensure_secrets(paths: LabPaths) -> None:
    if not paths.lab_key.exists():
        run(
            [
                "ssh-keygen",
                "-q",
                "-t",
                "ed25519",
                "-N",
                "",
                "-C",
                LAB_KEY_COMMENT,
                "-f",
                str(paths.lab_key),
            ]
        )
    for secret in (paths.k3s_token, paths.webhook_secret):
        if not secret.exists():
            write_private(secret, secrets.token_hex(SECRET_BYTES))


@dataclass(frozen=True)
class LabContext:
    paths: LabPaths
    platform: str
    system: str
    accel: str
    flake: str
    source: Path
    firmware_dir: Path
    plan: AddressPlan
