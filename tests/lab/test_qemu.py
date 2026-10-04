from pathlib import Path

import pytest
from vigil_lab.addresses import LabHost, parse_address_plan
from vigil_lab.proc import LabError
from vigil_lab.qemu import qemu_args
from vigil_lab.state import LabPaths

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
