import os
import shutil
import signal
import socket
import subprocess
import tempfile
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from vigil_lab import qemu
from vigil_lab.addresses import LabHost, parse_address_plan
from vigil_lab.proc import LabError, spawn, terminate
from vigil_lab.qemu import (
    BUILDER,
    SHUTDOWN_TIMEOUT_S,
    VM,
    exclusive_start,
    qemu_args,
    shutdown,
)
from vigil_lab.state import LabPaths

GUEST_SLEEP_SECONDS = "30"
MONITOR_RECV_BYTES = 64
MONITOR_ACCEPT_TIMEOUT_S = 10
POWERDOWN_COMMAND = b"system_powerdown\n"
STUBBORN_GUEST = "trap '' TERM; while :; do sleep 1; done"
ESCALATION_TIMEOUT_S = 0.2
ESCALATION_TERMINATE_TIMEOUT_S = 1
SLEEPERS: list[subprocess.Popen[bytes]] = []

FIXTURE = Path(__file__).parent / "fixtures" / "addresses.json"
PATHS = LabPaths(Path("/s"))
FIRMWARE = Path("/fw")
ISO = Path("/nix/store/x-installer.iso")
OVERLONG_ROOT = Path("/" + "a" * 120)


def _hosts() -> tuple[LabHost, LabHost]:
    plan = parse_address_plan(FIXTURE.read_text())
    return plan.control_plane, plan.workers[0]


def test_aarch64_worker_boots_edk2_on_hvf_with_the_hub_nic() -> None:
    _, worker = _hosts()
    assert qemu_args(
        worker, "aarch64-linux", "hvf", PATHS, FIRMWARE, PATHS.disk(worker.name)
    ) == [
        "qemu-system-aarch64",
        "-name",
        "vigil-worker-1",
        "-accel",
        "hvf",
        "-M",
        "virt",
        "-cpu",
        "host",
        "-drive",
        "if=pflash,format=raw,readonly=on,file=/fw/edk2-aarch64-code.fd",
        "-drive",
        "if=pflash,format=raw,file=/s/run/vigil-worker-1-vars.fd",
        "-m",
        "2048",
        "-smp",
        "2",
        "-drive",
        "if=virtio,format=qcow2,file=/s/run/vigil-worker-1.qcow2",
        "-netdev",
        "user,id=user0,hostfwd=tcp:127.0.0.1:2211-:22",
        "-device",
        "virtio-net-pci,netdev=user0,addr=0x8",
        "-netdev",
        "stream,id=hub0,server=off,reconnect-ms=1000,addr.type=unix,addr.path=/s/run/hub.sock",
        "-device",
        "virtio-net-pci,netdev=hub0,addr=0x9,mac=52:54:00:fa:00:11",
        "-chardev",
        "socket,id=ser0,path=/s/run/vigil-worker-1.serial,server=on,wait=off,logfile=/s/logs/vigil-worker-1-serial.log,logappend=on",
        "-serial",
        "chardev:ser0",
        "-monitor",
        "unix:/s/run/vigil-worker-1.monitor,server=on,wait=off",
        "-display",
        "none",
    ]


def test_x86_64_control_plane_boots_seabios_on_kvm_and_forwards_the_api() -> None:
    control_plane, _ = _hosts()
    args = qemu_args(
        control_plane,
        "x86_64-linux",
        "kvm",
        PATHS,
        FIRMWARE,
        PATHS.disk(control_plane.name),
    )
    assert args[:5] == [
        "qemu-system-x86_64",
        "-name",
        "vigil-control-plane-1",
        "-accel",
        "kvm",
    ]
    assert not any("pflash" in a for a in args)
    assert args[args.index("-M") + 1] == "pc"
    assert args[args.index("-m") + 1] == "3072"
    assert (
        "user,id=user0,hostfwd=tcp:127.0.0.1:2210-:22,hostfwd=tcp:127.0.0.1:16443-:6443"
        in args
    )
    assert "virtio-net-pci,netdev=hub0,addr=0x9,mac=52:54:00:fa:00:10" in args


def test_x86_64_install_attaches_the_iso_and_uses_the_virtio_console() -> None:
    _, worker = _hosts()
    disk = Path("/s/golden/vigil-worker-1.qcow2.part")
    args = qemu_args(worker, "x86_64-linux", "kvm", PATHS, FIRMWARE, disk, iso=ISO)
    assert f"if=virtio,format=qcow2,file={disk}" in args
    assert f"if=none,id=cd0,media=cdrom,readonly=on,file={ISO}" in args
    assert "scsi-cd,drive=cd0" in args
    assert "virtconsole,chardev=ser0" in args
    assert "chardev:ser0" not in args
    assert not any("hub0" in a for a in args)


def test_aarch64_install_uses_the_serial_console() -> None:
    _, worker = _hosts()
    args = qemu_args(
        worker,
        "aarch64-linux",
        "hvf",
        PATHS,
        FIRMWARE,
        PATHS.disk(worker.name),
        iso=ISO,
    )
    assert "scsi-cd,drive=cd0" in args
    assert "chardev:ser0" in args
    assert not any("virtconsole" in a for a in args)


def test_socket_paths_beyond_the_unix_limit_are_refused() -> None:
    with pytest.raises(LabError, match="XDG_STATE_HOME"):
        LabPaths(OVERLONG_ROOT).serial("vigil-worker-1")


@pytest.fixture(autouse=True)
def _reap_sleepers() -> Iterator[None]:
    yield
    for process in SLEEPERS:
        process.kill()
        process.wait()
    SLEEPERS.clear()


def _sleeper(paths: LabPaths, pid_file: Path) -> None:
    SLEEPERS.append(
        spawn(
            ["sleep", GUEST_SLEEP_SECONDS],
            pid_file=pid_file,
            log_file=paths.log("sleeper"),
        )
    )


def test_start_guard_refuses_the_builder_while_a_vm_runs(tmp_path: Path) -> None:
    paths = LabPaths(tmp_path)
    paths.ensure()
    _sleeper(paths, paths.vm_pid("vigil-worker-1"))
    with pytest.raises(LabError, match="lab down"):
        exclusive_start(paths, BUILDER)
    exclusive_start(paths, VM)


def test_start_guard_refuses_a_vm_while_the_builder_runs(tmp_path: Path) -> None:
    paths = LabPaths(tmp_path)
    paths.ensure()
    _sleeper(paths, paths.pid(BUILDER))
    with pytest.raises(LabError, match="image builder"):
        exclusive_start(paths, VM)


def test_start_guard_refuses_a_second_builder(tmp_path: Path) -> None:
    paths = LabPaths(tmp_path)
    paths.ensure()
    _sleeper(paths, paths.pid(BUILDER))
    with pytest.raises(LabError, match="already running"):
        exclusive_start(paths, BUILDER)


def test_start_guard_ignores_a_pid_file_of_an_unrelated_process(
    tmp_path: Path,
) -> None:
    paths = LabPaths(tmp_path)
    paths.ensure()
    paths.vm_pid("vigil-worker-1").write_text(str(os.getpid()))
    exclusive_start(paths, BUILDER)
    assert not paths.vm_pid("vigil-worker-1").exists()


@pytest.fixture
def short_paths() -> Iterator[LabPaths]:
    directory = Path(tempfile.mkdtemp(prefix="vl", dir="/tmp"))
    paths = LabPaths(directory)
    paths.ensure()
    yield paths
    shutil.rmtree(directory, ignore_errors=True)


def test_shutdown_powers_the_guest_down_through_the_monitor(
    short_paths: LabPaths,
) -> None:
    name = "vigil-worker-1"
    guest = spawn(
        ["sleep", GUEST_SLEEP_SECONDS],
        pid_file=short_paths.vm_pid(name),
        log_file=short_paths.log("guest"),
    )
    received: list[bytes] = []
    monitor = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    monitor.settimeout(MONITOR_ACCEPT_TIMEOUT_S)
    monitor.bind(str(short_paths.monitor(name)))
    monitor.listen(1)

    def serve_monitor() -> None:
        connection, _ = monitor.accept()
        with connection:
            received.append(connection.recv(MONITOR_RECV_BYTES))
        guest.terminate()

    server = threading.Thread(target=serve_monitor, daemon=True)
    server.start()
    started = time.monotonic()
    try:
        shutdown(short_paths, name)
    finally:
        server.join(timeout=MONITOR_ACCEPT_TIMEOUT_S)
        monitor.close()
    assert received == [POWERDOWN_COMMAND]
    assert time.monotonic() - started < SHUTDOWN_TIMEOUT_S
    assert not short_paths.vm_pid(name).exists()


def test_shutdown_escalates_to_sigkill_when_the_monitor_is_unreachable(
    short_paths: LabPaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    name = "vigil-worker-1"
    guest = spawn(
        ["sh", "-c", STUBBORN_GUEST],
        pid_file=short_paths.vm_pid(name),
        log_file=short_paths.log("guest"),
    )
    SLEEPERS.append(guest)
    monkeypatch.setattr(
        qemu,
        "terminate",
        lambda pid_file: terminate(pid_file, timeout_s=ESCALATION_TERMINATE_TIMEOUT_S),
    )
    shutdown(short_paths, name, timeout_s=ESCALATION_TIMEOUT_S)
    assert not short_paths.vm_pid(name).exists()
    assert guest.wait(timeout=ESCALATION_TERMINATE_TIMEOUT_S) == -signal.SIGKILL


def test_shutdown_removes_the_pid_file_of_a_dead_guest(short_paths: LabPaths) -> None:
    short_paths.vm_pid("vigil-worker-1").write_text("999999\nstale")
    shutdown(short_paths, "vigil-worker-1")
    assert not short_paths.vm_pid("vigil-worker-1").exists()
