from pathlib import Path

import pytest
from vigil_lab.preflight import (
    MIN_FREE_MEMORY_PERCENT,
    accelerator,
    check_memory,
    guest_system,
    run_memory_preflight,
)
from vigil_lab.proc import LabError

OWNER_READ_WRITE = 0o600


def _memory_pressure(free_percent: int) -> str:
    return (
        "The system has 17179869184 (4194304 pages with a page size of 4096).\n"
        f"System-wide memory free percentage: {free_percent}%\n"
    )


def test_guest_system_refuses_unsupported_hosts() -> None:
    assert guest_system("darwin", "arm64") == "aarch64-linux"
    with pytest.raises(LabError, match="Apple silicon"):
        guest_system("linux", "aarch64")


def test_accelerator_on_macos_requires_hv_support() -> None:
    assert accelerator("darwin", hv_support="1\n") == "hvf"
    with pytest.raises(LabError, match="kern.hv_support"):
        accelerator("darwin", hv_support="0")


def test_accelerator_on_linux_requires_a_read_write_kvm_device(
    tmp_path: Path,
) -> None:
    device = tmp_path / "kvm"
    device.write_text("")
    device.chmod(OWNER_READ_WRITE)
    assert accelerator("linux", kvm_device=device) == "kvm"
    with pytest.raises(LabError, match=str(tmp_path / "absent")):
        accelerator("linux", kvm_device=tmp_path / "absent")


def test_check_memory_needs_the_named_free_percentage() -> None:
    check_memory(_memory_pressure(MIN_FREE_MEMORY_PERCENT))
    with pytest.raises(LabError, match=f"{MIN_FREE_MEMORY_PERCENT}%"):
        check_memory(_memory_pressure(MIN_FREE_MEMORY_PERCENT - 1))
    with pytest.raises(LabError, match="memory_pressure"):
        check_memory("unexpected output\n")


def test_memory_preflight_is_a_no_op_off_macos(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(command: list[str]) -> str:
        raise AssertionError(command)

    monkeypatch.setattr("vigil_lab.preflight.run", refuse)
    run_memory_preflight("linux")


def test_memory_preflight_on_macos_reads_memory_pressure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "vigil_lab.preflight.run",
        lambda command: _memory_pressure(MIN_FREE_MEMORY_PERCENT - 1),
    )
    with pytest.raises(LabError, match=f"{MIN_FREE_MEMORY_PERCENT}%"):
        run_memory_preflight("darwin")
