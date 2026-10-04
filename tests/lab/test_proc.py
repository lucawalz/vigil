from pathlib import Path

import pytest
from vigil_lab.proc import LabError, run, wait_until

SHORT_TIMEOUT_S = 0.05
SHORT_INTERVAL_S = 0.01


def test_run_raises_with_the_stderr_tail() -> None:
    with pytest.raises(LabError, match="boom"):
        run(["sh", "-c", "echo boom >&2; exit 3"])


def test_run_sends_stderr_to_the_log_file(tmp_path: Path) -> None:
    log = tmp_path / "logs" / "step.log"
    with pytest.raises(LabError, match=str(log)):
        run(["sh", "-c", "echo detail >&2; exit 1"], log_file=log)
    assert "detail" in log.read_text()


def test_wait_until_times_out_with_the_description() -> None:
    with pytest.raises(LabError, match="the impossible"):
        wait_until(
            lambda: False,
            timeout_s=SHORT_TIMEOUT_S,
            description="the impossible",
            interval_s=SHORT_INTERVAL_S,
        )
