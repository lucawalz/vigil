import stat
from pathlib import Path

import pytest
from vigil_lab.proc import LabError
from vigil_lab.state import LabPaths, load_settings, write_private

PRIVATE_DIR = 0o700
PRIVATE_FILE = 0o600


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_ensure_creates_a_private_state_directory(tmp_path: Path) -> None:
    paths = LabPaths(tmp_path / "lab")
    paths.ensure()
    assert _mode(paths.root) == PRIVATE_DIR
    assert paths.run.is_dir()


def test_write_private_uses_owner_only_mode(tmp_path: Path) -> None:
    target = tmp_path / "secret"
    write_private(target, "s")
    assert _mode(target) == PRIVATE_FILE


def test_load_settings_names_lab_up(tmp_path: Path) -> None:
    with pytest.raises(LabError, match="lab up"):
        load_settings(LabPaths(tmp_path))
