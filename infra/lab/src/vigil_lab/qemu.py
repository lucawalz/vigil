from __future__ import annotations

from pathlib import Path

from vigil_lab.addresses import CONTROL_PLANE_ROLE, LabHost
from vigil_lab.state import LabPaths

AARCH64_LINUX = "aarch64-linux"
X86_64_LINUX = "x86_64-linux"
QEMU_BINARIES = {
    AARCH64_LINUX: "qemu-system-aarch64",
    X86_64_LINUX: "qemu-system-x86_64",
}
MACHINES = {AARCH64_LINUX: "virt", X86_64_LINUX: "pc"}
AARCH64_FIRMWARE = "edk2-aarch64-code.fd"
AARCH64_VARS_TEMPLATE = "edk2-arm-vars.fd"
CONTROL_PLANE_MEMORY_MIB = 3072
WORKER_MEMORY_MIB = 2048
VCPUS = 2
USER_NIC_PCI_ADDR = "0x8"
HUB_NIC_PCI_ADDR = "0x9"
LAB_MAC_PREFIX = "52:54:00:fa:00"
LOOPBACK = "127.0.0.1"
GUEST_SSH_PORT = 22
GUEST_API_PORT = 6443
API_FORWARD_PORT = 16443
HUB_RECONNECT_MS = 1000


def _user_netdev(host: LabHost) -> str:
    forwards = [f"hostfwd=tcp:{LOOPBACK}:{host.ssh_port}-:{GUEST_SSH_PORT}"]
    if host.role == CONTROL_PLANE_ROLE:
        forwards.append(f"hostfwd=tcp:{LOOPBACK}:{API_FORWARD_PORT}-:{GUEST_API_PORT}")
    return ",".join(["user", "id=user0", *forwards])


def qemu_args(
    host: LabHost,
    system: str,
    accel: str,
    paths: LabPaths,
    firmware_dir: Path,
    disk: Path,
    iso: Path | None = None,
) -> list[str]:
    memory = (
        CONTROL_PLANE_MEMORY_MIB
        if host.role == CONTROL_PLANE_ROLE
        else WORKER_MEMORY_MIB
    )
    args = [QEMU_BINARIES[system], "-name", host.name, "-accel", accel]
    args += ["-M", MACHINES[system], "-cpu", "host"]
    if system == AARCH64_LINUX:
        args += [
            "-drive",
            f"if=pflash,format=raw,readonly=on,file={firmware_dir / AARCH64_FIRMWARE}",
            "-drive",
            f"if=pflash,format=raw,file={paths.vars(host.name)}",
        ]
    args += [
        "-m",
        str(memory),
        "-smp",
        str(VCPUS),
        "-drive",
        f"if=virtio,format=qcow2,file={disk}",
        "-netdev",
        _user_netdev(host),
        "-device",
        f"virtio-net-pci,netdev=user0,addr={USER_NIC_PCI_ADDR}",
    ]
    if iso is None:
        args += [
            "-netdev",
            f"stream,id=hub0,server=off,reconnect-ms={HUB_RECONNECT_MS},"
            f"addr.type=unix,addr.path={paths.hub_socket}",
            "-device",
            f"virtio-net-pci,netdev=hub0,addr={HUB_NIC_PCI_ADDR},mac={LAB_MAC_PREFIX}:{host.index:02d}",
        ]
    else:
        args += [
            "-device",
            "virtio-scsi-pci,id=scsi0",
            "-drive",
            f"if=none,id=cd0,media=cdrom,readonly=on,file={iso}",
            "-device",
            "scsi-cd,drive=cd0",
        ]
    args += [
        "-chardev",
        f"socket,id=ser0,path={paths.serial(host.name)},server=on,wait=off,"
        f"logfile={paths.serial_log(host.name)},logappend=on",
    ]
    if iso is not None and system == X86_64_LINUX:
        args += [
            "-device",
            "virtio-serial-pci,id=vser0",
            "-device",
            "virtconsole,chardev=ser0",
        ]
    else:
        args += ["-serial", "chardev:ser0"]
    args += [
        "-monitor",
        f"unix:{paths.monitor(host.name)},server=on,wait=off",
        "-display",
        "none",
    ]
    return args
