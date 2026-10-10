from __future__ import annotations

import hashlib
import json
import shutil
import socket
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from vigil_lab import builder, qemu
from vigil_lab.addresses import LabHost
from vigil_lab.guest import guest_ssh_args, wait_for_ssh
from vigil_lab.preflight import DARWIN
from vigil_lab.proc import LabError, probe, run, terminate, wait_until
from vigil_lab.state import PRIVATE_DIR_MODE, LabContext, LabPaths, write_private

ISO_VERSION = "26.11pre1083223.c59305bab206"
ISO_RELEASE = f"nixos-{ISO_VERSION}"
ISO_BASE_URL = f"https://releases.nixos.org/nixos/unstable/{ISO_RELEASE}"


@dataclass(frozen=True)
class InstallerIso:
    url: str
    sha256: str


INSTALLER_ISOS = {
    qemu.AARCH64_LINUX: InstallerIso(
        f"{ISO_BASE_URL}/nixos-minimal-{ISO_VERSION}-aarch64-linux.iso",
        "c6da976f88f09798635e1130997e78c6332167acab0fee7c795833aabf754942",
    ),
    qemu.X86_64_LINUX: InstallerIso(
        f"{ISO_BASE_URL}/nixos-minimal-{ISO_VERSION}-x86_64-linux.iso",
        "4589ab34f100ab244af1ec2c094020749cfbfcccc488595b57130b93b68229c9",
    ),
}
DISK_SIZE = "10G"
INSTALLER_PROMPT = "nixos@nixos"
INSTALLER_PROMPT_TIMEOUT_S = 300.0
INSTALLER_SSH_TIMEOUT_S = 180.0
INSTALLER_POWEROFF_TIMEOUT_S = 120.0
CONSOLE_SETTLE_S = 3.0
INJECT_KEY_COMMAND = (
    "sudo install -d -m700 /root/.ssh"
    " && echo '{key}' | sudo tee /root/.ssh/authorized_keys > /dev/null"
    " && sudo sha256sum /root/.ssh/authorized_keys\r"
)
INTERRUPT = "\x03"
CLEAR_LINE = "\x15"
CONSOLE_CHUNK_BYTES = 16
CONSOLE_CHUNK_PAUSE_S = 0.05
KEY_ATTEMPTS = 3
KEY_CONFIRM_TIMEOUT_S = 20.0
KEY_POLL_INTERVAL_S = 0.5
TOPLEVEL = "toplevel"
DISKO_SCRIPT = "diskoScript"
READ_ONLY_MODE = 0o444
WRITABLE_MODE = 0o644


@dataclass(frozen=True)
class HostClosure:
    toplevel: str
    disko: str


def _installable(flake: str, attr: str, output: str) -> str:
    return f"{flake}#nixosConfigurations.{attr}.config.system.build.{output}"


def fetch_iso(iso: InstallerIso) -> Path:
    out = run(
        [
            "nix",
            "store",
            "prefetch-file",
            "--json",
            "--expected-hash",
            f"sha256:{iso.sha256}",
            iso.url,
        ]
    )
    return Path(json.loads(out)["storePath"])


def eval_closure(flake: str, attr: str) -> HostClosure:
    return HostClosure(
        toplevel=run(
            ["nix", "eval", "--raw", _installable(flake, attr, TOPLEVEL)]
        ).strip(),
        disko=run(
            ["nix", "eval", "--raw", _installable(flake, attr, DISKO_SCRIPT)]
        ).strip(),
    )


def realise(ctx: LabContext, hosts: list[LabHost]) -> None:
    targets = [
        _installable(ctx.flake, host.flake_attr(ctx.system), output)
        for host in hosts
        for output in (TOPLEVEL, DISKO_SCRIPT)
    ]
    with builder.build_env(ctx) as env:
        run(
            ["nix", "build", "--no-link", *targets],
            env=env,
            log_file=ctx.paths.log("build"),
        )


def clone(platform: str, src: Path, dst: Path) -> None:
    dst.unlink(missing_ok=True)
    if platform == DARWIN:
        run(["/bin/cp", "-c", str(src), str(dst)])
    else:
        run(["cp", "--reflink=auto", str(src), str(dst)])
    dst.chmod(WRITABLE_MODE)


def fresh_vars(ctx: LabContext, host: LabHost) -> None:
    if ctx.system == qemu.AARCH64_LINUX:
        clone(
            ctx.platform,
            ctx.firmware_dir / qemu.AARCH64_VARS_TEMPLATE,
            ctx.paths.vars(host.name),
        )


def golden_is_current(paths: LabPaths, host: LabHost, closure: HostClosure) -> bool:
    meta = paths.golden_meta(host.name)
    return (
        paths.golden_disk(host.name).exists()
        and meta.exists()
        and json.loads(meta.read_text()) == asdict(closure)
    )


def write_extra_files(directory: Path, token: str, authorized_key: str) -> None:
    shutil.rmtree(directory, ignore_errors=True)
    write_private(directory / "etc" / "k3s" / "token", token)
    root_dir = directory / "root"
    ssh_dir = root_dir / ".ssh"
    write_private(ssh_dir / "authorized_keys", f"{authorized_key}\n")
    root_dir.chmod(PRIVATE_DIR_MODE)
    ssh_dir.chmod(PRIVATE_DIR_MODE)


def _send_console(path: Path, line: str) -> None:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.connect(str(path))
        client.sendall(INTERRUPT.encode())
        time.sleep(CONSOLE_CHUNK_PAUSE_S)
        data = (CLEAR_LINE + line).encode()
        for start in range(0, len(data), CONSOLE_CHUNK_BYTES):
            client.sendall(data[start : start + CONSOLE_CHUNK_BYTES])
            time.sleep(CONSOLE_CHUNK_PAUSE_S)


def _read(path: Path) -> str:
    return path.read_text(errors="replace") if path.exists() else ""


def _log_size(path: Path) -> int:
    return path.stat().st_size if path.exists() else 0


def _logged_after(path: Path, offset: int) -> bytes:
    return path.read_bytes()[offset:] if path.exists() else b""


def _key_confirmed(console_log: Path, offset: int, digest: str) -> bool:
    try:
        wait_until(
            lambda: digest.encode() in _logged_after(console_log, offset),
            KEY_CONFIRM_TIMEOUT_S,
            "the installer key confirmation",
            KEY_POLL_INTERVAL_S,
        )
    except LabError:
        return False
    return True


def _inject_key(paths: LabPaths, host: LabHost, public_key: str) -> None:
    console_log = paths.serial_log(host.name)
    line = INJECT_KEY_COMMAND.format(key=public_key)
    digest = hashlib.sha256(f"{public_key}\n".encode()).hexdigest()
    for _ in range(KEY_ATTEMPTS):
        offset = _log_size(console_log)
        _send_console(paths.serial(host.name), line)
        if _key_confirmed(console_log, offset, digest):
            return
    raise LabError(
        f"the {host.name} installer console did not confirm the key command"
        f" after {KEY_ATTEMPTS} attempts; see {console_log}"
    )


def install(
    ctx: LabContext, host: LabHost, closure: HostClosure, dst: Path, iso: Path
) -> None:
    paths = ctx.paths
    partial = dst.with_name(f"{dst.name}.part")
    partial.unlink(missing_ok=True)
    console_log = paths.serial_log(host.name)
    console_log.unlink(missing_ok=True)
    run(["qemu-img", "create", "-q", "-f", "qcow2", str(partial), DISK_SIZE])
    fresh_vars(ctx, host)
    extra = paths.run / f"{host.name}-extra"
    public_key = paths.lab_key.with_suffix(".pub").read_text().strip()
    try:
        write_extra_files(extra, paths.k3s_token.read_text().strip(), public_key)
        process = qemu.start(ctx, host, disk=partial, iso=iso)
        wait_until(
            lambda: INSTALLER_PROMPT in _read(console_log),
            INSTALLER_PROMPT_TIMEOUT_S,
            f"the {host.name} installer shell",
        )
        time.sleep(CONSOLE_SETTLE_S)
        _inject_key(paths, host, public_key)
        wait_for_ssh(paths, host, INSTALLER_SSH_TIMEOUT_S)
        run(
            [
                "nixos-anywhere",
                "--build-on",
                "remote",
                "--phases",
                "kexec,disko,install",
                "--extra-files",
                str(extra),
                "--store-paths",
                closure.disko,
                closure.toplevel,
                "-i",
                str(paths.lab_key),
                "-p",
                str(host.ssh_port),
                "--ssh-option",
                "UserKnownHostsFile=/dev/null",
                "--ssh-option",
                "StrictHostKeyChecking=no",
                "--ssh-option",
                "BatchMode=yes",
                f"root@{qemu.LOOPBACK}",
            ],
            log_file=paths.log(f"{host.name}-install"),
        )
        probe(guest_ssh_args(paths, host, "poweroff"), INSTALLER_POWEROFF_TIMEOUT_S)
        process.wait(timeout=INSTALLER_POWEROFF_TIMEOUT_S)
    except BaseException:
        terminate(paths.vm_pid(host.name))
        partial.unlink(missing_ok=True)
        raise
    finally:
        shutil.rmtree(extra, ignore_errors=True)
        paths.vm_pid(host.name).unlink(missing_ok=True)
    partial.rename(dst)


def _closures(ctx: LabContext, hosts: list[LabHost]) -> dict[str, HostClosure]:
    return {
        host.name: eval_closure(ctx.flake, host.flake_attr(ctx.system))
        for host in hosts
    }


def ensure_golden(ctx: LabContext, hosts: list[LabHost]) -> None:
    closures = _closures(ctx, hosts)
    stale = [
        host
        for host in hosts
        if not golden_is_current(ctx.paths, host, closures[host.name])
    ]
    if not stale:
        return
    realise(ctx, stale)
    iso = fetch_iso(INSTALLER_ISOS[ctx.system])
    for host in stale:
        disk = ctx.paths.golden_disk(host.name)
        if disk.exists():
            disk.chmod(WRITABLE_MODE)
            disk.unlink()
        install(ctx, host, closures[host.name], disk, iso)
        disk.chmod(READ_ONLY_MODE)
        ctx.paths.golden_meta(host.name).write_text(
            json.dumps(asdict(closures[host.name]))
        )


def install_in_place(ctx: LabContext, hosts: list[LabHost]) -> None:
    closures = _closures(ctx, hosts)
    realise(ctx, hosts)
    iso = fetch_iso(INSTALLER_ISOS[ctx.system])
    for host in hosts:
        install(ctx, host, closures[host.name], ctx.paths.disk(host.name), iso)


def clone_golden(ctx: LabContext, host: LabHost) -> None:
    golden = ctx.paths.golden_disk(host.name)
    if not golden.exists():
        raise LabError(f"no golden disk for {host.name}; run `lab up` first")
    clone(ctx.platform, golden, ctx.paths.disk(host.name))
    fresh_vars(ctx, host)
