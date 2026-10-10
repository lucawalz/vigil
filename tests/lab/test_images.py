import hashlib
import json
import re
import stat
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Self

import pytest
from vigil_lab import images
from vigil_lab.addresses import LabHost, parse_address_plan
from vigil_lab.guest import guest_ssh_args
from vigil_lab.images import HostClosure, golden_is_current, write_extra_files
from vigil_lab.preflight import DARWIN, LINUX
from vigil_lab.proc import LabError
from vigil_lab.qemu import X86_64_LINUX
from vigil_lab.state import LabContext, LabPaths

FIXTURE = Path(__file__).parent / "fixtures" / "addresses.json"
CLOSURE = HostClosure(toplevel="/nix/store/t-nixos-system", disko="/nix/store/d-disko")
PRIVATE_FILE = 0o600
PRIVATE_DIR = 0o700
STORE_PATH = "/nix/store/abc-nixos.iso"


def test_golden_is_current_compares_the_recorded_store_paths(tmp_path: Path) -> None:
    paths = LabPaths(tmp_path)
    paths.ensure()
    worker = parse_address_plan(FIXTURE.read_text()).workers[0]
    assert not golden_is_current(paths, worker, CLOSURE)
    paths.golden_disk(worker.name).write_bytes(b"disk")
    paths.golden_meta(worker.name).write_text(json.dumps(asdict(CLOSURE)))
    assert golden_is_current(paths, worker, CLOSURE)
    assert not golden_is_current(
        paths, worker, HostClosure(toplevel="/nix/store/other", disko=CLOSURE.disko)
    )


def test_extra_files_hold_the_token_and_key_privately(tmp_path: Path) -> None:
    extra = tmp_path / "extra"
    write_extra_files(extra, "token", "ssh-ed25519 AAAA vigil-lab")
    token = extra / "etc" / "k3s" / "token"
    keys = extra / "root" / ".ssh" / "authorized_keys"
    assert token.read_text() == "token"
    assert keys.read_text() == "ssh-ed25519 AAAA vigil-lab\n"
    assert stat.S_IMODE(token.stat().st_mode) == PRIVATE_FILE
    assert stat.S_IMODE(keys.parent.stat().st_mode) == PRIVATE_DIR
    assert stat.S_IMODE(keys.parent.parent.stat().st_mode) == PRIVATE_DIR


def test_fetch_iso_pins_the_expected_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[Sequence[str]] = []

    def fake_run(args: Sequence[str], **_: object) -> str:
        calls.append(args)
        return json.dumps({"storePath": STORE_PATH})

    monkeypatch.setattr(images, "run", fake_run)
    iso = images.INSTALLER_ISOS[X86_64_LINUX]
    assert images.fetch_iso(iso) == Path(STORE_PATH)
    args = calls[0]
    assert args[args.index("--expected-hash") + 1] == f"sha256:{iso.sha256}"


def test_failed_start_leaves_no_partial_disk_or_token_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    paths = LabPaths(tmp_path)
    paths.ensure()
    paths.lab_key.with_suffix(".pub").write_text("ssh-ed25519 AAAA vigil-lab\n")
    paths.k3s_token.write_text("token")
    plan = parse_address_plan(FIXTURE.read_text())
    ctx = LabContext(
        paths, LINUX, X86_64_LINUX, "kvm", "flake", tmp_path, tmp_path, plan
    )
    worker = plan.workers[0]
    dst = paths.disk(worker.name)
    partial = dst.with_name(f"{dst.name}.part")

    def fake_run(args: Sequence[str], **_: object) -> str:
        partial.write_bytes(b"disk")
        return ""

    def failing_start(*_: object, **__: object) -> None:
        raise LabError("another vm is starting")

    monkeypatch.setattr(images, "run", fake_run)
    monkeypatch.setattr(images.qemu, "start", failing_start)
    with pytest.raises(LabError):
        images.install(ctx, worker, CLOSURE, dst, tmp_path / "installer.iso")
    assert not partial.exists()
    assert not (paths.run / f"{worker.name}-extra").exists()


def test_install_keeps_nixos_anywhere_ssh_from_asking_for_a_password(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    paths = LabPaths(tmp_path)
    paths.ensure()
    paths.lab_key.with_suffix(".pub").write_text("ssh-ed25519 AAAA vigil-lab\n")
    paths.k3s_token.write_text("token")
    plan = parse_address_plan(FIXTURE.read_text())
    ctx = LabContext(
        paths, LINUX, X86_64_LINUX, "kvm", "flake", tmp_path, tmp_path, plan
    )
    worker = plan.workers[0]
    dst = paths.disk(worker.name)
    partial = dst.with_name(f"{dst.name}.part")
    calls: list[list[str]] = []
    order: list[str] = []

    def fake_run(args: Sequence[str], **_: object) -> str:
        calls.append(list(args))
        partial.write_bytes(b"disk")
        return ""

    class FakeProcess:
        def wait(self, timeout: float) -> int:
            return 0

    monkeypatch.setattr(images, "run", fake_run)
    monkeypatch.setattr(LabPaths, "serial", lambda self, name: self.run / name)
    monkeypatch.setattr(images, "fresh_vars", lambda *_: None)
    monkeypatch.setattr(images.qemu, "start", lambda *_, **__: FakeProcess())
    monkeypatch.setattr(images, "wait_until", lambda *_: None)
    monkeypatch.setattr(images.time, "sleep", lambda _: None)
    monkeypatch.setattr(images, "_inject_key", lambda *_: order.append("key"))
    monkeypatch.setattr(images, "wait_for_ssh", lambda *_: order.append("ssh"))
    monkeypatch.setattr(images, "probe", lambda *_: True)
    images.install(ctx, worker, CLOSURE, dst, tmp_path / "installer.iso")
    assert order == ["key", "ssh"]
    anywhere = next(args for args in calls if args[0] == "nixos-anywhere")
    options = [
        anywhere[i + 1] for i, arg in enumerate(anywhere) if arg == "--ssh-option"
    ]
    assert "BatchMode=yes" in options


PUBLIC_KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIvigil vigil-lab"
DROPPED_WRITE = 5
KEY_FILE = "/root/.ssh/authorized_keys"
QUOTED_KEY = re.compile(r"echo '([^']*)'")


class FakeConsole:
    def __init__(self, log: Path, dropping_attempts: int) -> None:
        self.log = log
        self.dropping_attempts = dropping_attempts
        self.attempts = 0
        self.attempt_chunks: list[list[bytes]] = []
        self.received = ""

    def __call__(self, *_: object) -> Self:
        return self

    def __enter__(self) -> Self:
        self.attempts += 1
        self.attempt_chunks.append([])
        self.received = ""
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def connect(self, _: str) -> None:
        return None

    def sendall(self, data: bytes) -> None:
        writes = self.attempt_chunks[-1]
        writes.append(data)
        lossy = self.attempts <= self.dropping_attempts
        if lossy and len(writes) == DROPPED_WRITE:
            return
        self.received += data.decode()
        with self.log.open("a") as log:
            log.write(data.decode())
            if self.received.endswith("\r"):
                log.write(self.run_shell())

    def run_shell(self) -> str:
        line = self.received.rpartition(images.CLEAR_LINE)[2]
        if images.CLEAR_LINE not in self.received:
            return ""
        match = QUOTED_KEY.search(line)
        if match is None or line != images.INJECT_KEY_COMMAND.format(key=match[1]):
            return ""
        digest = hashlib.sha256(f"{match[1]}\n".encode()).hexdigest()
        return f"\n{digest}  {KEY_FILE}\n"


def _console_lab(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, dropping_attempts: int
) -> tuple[LabPaths, FakeConsole, LabHost]:
    paths = LabPaths(tmp_path)
    paths.ensure()
    monkeypatch.setattr(LabPaths, "serial", lambda self, name: self.run / name)
    worker = parse_address_plan(FIXTURE.read_text()).workers[0]
    console = FakeConsole(paths.serial_log(worker.name), dropping_attempts)
    monkeypatch.setattr(images.socket, "socket", console)
    monkeypatch.setattr(images, "CONSOLE_CHUNK_PAUSE_S", 0.0)
    monkeypatch.setattr(images, "KEY_CONFIRM_TIMEOUT_S", 0.05)
    monkeypatch.setattr(images, "KEY_POLL_INTERVAL_S", 0.01)
    return paths, console, worker


def test_key_command_is_confirmed_on_a_lossless_console(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    paths, console, worker = _console_lab(monkeypatch, tmp_path, 0)
    images._inject_key(paths, worker, PUBLIC_KEY)
    assert console.attempts == 1


def test_key_command_is_resent_after_loss_inside_the_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    paths, console, worker = _console_lab(monkeypatch, tmp_path, 1)
    images._inject_key(paths, worker, PUBLIC_KEY)
    assert console.attempts == 2


def test_key_command_fails_naming_host_and_serial_log_when_always_lossy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    paths, console, worker = _console_lab(monkeypatch, tmp_path, 99)
    with pytest.raises(LabError) as caught:
        images._inject_key(paths, worker, PUBLIC_KEY)
    assert console.attempts == images.KEY_ATTEMPTS
    assert worker.name in str(caught.value)
    assert str(paths.serial_log(worker.name)) in str(caught.value)


def test_every_attempt_interrupts_then_clears_the_line_in_small_chunks(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    paths, console, worker = _console_lab(monkeypatch, tmp_path, 1)
    images._inject_key(paths, worker, PUBLIC_KEY)
    assert len(console.attempt_chunks) == 2
    for writes in console.attempt_chunks:
        assert writes[0] == images.INTERRUPT.encode()
        assert writes[1][:1] == images.CLEAR_LINE.encode()
        assert all(len(chunk) <= images.CONSOLE_CHUNK_BYTES for chunk in writes)


@pytest.mark.parametrize(
    ("platform", "expected"),
    [(DARWIN, ["/bin/cp", "-c"]), (LINUX, ["cp", "--reflink=auto"])],
)
def test_clone_uses_the_copy_on_write_flavour_of_the_platform(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    platform: str,
    expected: list[str],
) -> None:
    seen: list[list[str]] = []
    src, dst = tmp_path / "src", tmp_path / "dst"
    src.write_bytes(b"d")

    def fake_run(args: Sequence[str], **_: object) -> str:
        seen.append(list(args))
        dst.write_bytes(b"d")
        return ""

    monkeypatch.setattr(images, "run", fake_run)
    images.clone(platform, src, dst)
    assert seen == [[*expected, str(src), str(dst)]]
    assert stat.S_IMODE(dst.stat().st_mode) == images.WRITABLE_MODE


def test_guest_ssh_ignores_user_config_and_targets_the_forwarded_port(
    tmp_path: Path,
) -> None:
    paths = LabPaths(tmp_path)
    worker = parse_address_plan(FIXTURE.read_text()).workers[0]
    args = guest_ssh_args(paths, worker, "true")
    assert args[:3] == ["ssh", "-F", "/dev/null"]
    assert args[args.index("-p") + 1] == str(worker.ssh_port)
    assert args[-2:] == ["root@127.0.0.1", "true"]


def test_guest_ssh_never_asks_for_a_password(tmp_path: Path) -> None:
    paths = LabPaths(tmp_path)
    worker = parse_address_plan(FIXTURE.read_text()).workers[0]
    args = guest_ssh_args(paths, worker, "true")
    assert args[args.index("BatchMode=yes") - 1] == "-o"
