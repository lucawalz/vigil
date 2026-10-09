from __future__ import annotations

import os
import re
from pathlib import Path

from vigil_lab.proc import LabError, run
from vigil_lab.qemu import AARCH64_LINUX, X86_64_LINUX

DARWIN = "darwin"
LINUX = "linux"
GUEST_SYSTEMS = {(DARWIN, "arm64"): AARCH64_LINUX, (LINUX, "x86_64"): X86_64_LINUX}
HVF = "hvf"
KVM = "kvm"
KVM_DEVICE = Path("/dev/kvm")
HV_SUPPORTED = "1"
MIN_FREE_MEMORY_PERCENT = 45
FREE_PERCENT_RE = re.compile(r"System-wide memory free percentage: (\d+)%")


def guest_system(platform: str, machine: str) -> str:
    try:
        return GUEST_SYSTEMS[(platform, machine)]
    except KeyError:
        raise LabError(
            "the lab runs on Apple silicon macOS or x86_64 Linux, "
            f"not {platform}/{machine}"
        ) from None


def accelerator(
    platform: str, *, hv_support: str = "", kvm_device: Path = KVM_DEVICE
) -> str:
    if platform == DARWIN:
        if hv_support.strip() != HV_SUPPORTED:
            raise LabError(
                "sysctl kern.hv_support is not 1; the lab needs Hypervisor.framework"
            )
        return HVF
    if not os.access(kvm_device, os.R_OK | os.W_OK):
        raise LabError(
            f"{kvm_device} is missing or not read-write for this user; "
            "enable KVM and join the kvm group"
        )
    return KVM


def check_memory(memory_pressure_output: str) -> None:
    match = FREE_PERCENT_RE.search(memory_pressure_output)
    if match is None:
        raise LabError("memory_pressure printed no free memory percentage")
    free_percent = int(match.group(1))
    if free_percent < MIN_FREE_MEMORY_PERCENT:
        raise LabError(
            f"memory_pressure reports {free_percent}% free memory, "
            f"the lab needs at least {MIN_FREE_MEMORY_PERCENT}%; "
            "close memory-heavy applications and retry"
        )


def run_preflight(platform: str) -> str:
    if platform != DARWIN:
        return accelerator(platform)
    return accelerator(platform, hv_support=run(["sysctl", "-n", "kern.hv_support"]))


def run_memory_preflight(platform: str) -> None:
    if platform == DARWIN:
        check_memory(run(["memory_pressure"]))
