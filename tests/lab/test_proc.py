import subprocess
from pathlib import Path

import pytest
from vigil_lab.proc import (
    LabError,
    _start_stamp,  # pyright: ignore[reportPrivateUsage]
    pid_alive,
    run,
    spawn,
    stat_start_ticks,
    terminate,
    wait_until,
)

SHORT_TIMEOUT_S = 0.05
SHORT_INTERVAL_S = 0.01
TERMINATE_TEST_TIMEOUT_S = 5
SLEEP_SECONDS = "30"


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


def test_spawn_records_a_live_pid_and_terminate_stops_it(tmp_path: Path) -> None:
    pid_file = tmp_path / "sleeper.pid"
    spawn(
        ["sleep", SLEEP_SECONDS],
        pid_file=pid_file,
        log_file=tmp_path / "sleeper.log",
    )
    assert pid_alive(pid_file)
    terminate(pid_file, timeout_s=TERMINATE_TEST_TIMEOUT_S)
    assert not pid_file.exists()


def _stamp(pid: int) -> str:
    return run(["ps", "-o", "lstart=", "-p", str(pid)]).strip()


def test_stat_start_ticks_reads_field_22_past_a_hostile_comm() -> None:
    fields = " ".join(str(number * 10) for number in range(4, 53))
    assert stat_start_ticks(f"1234 (a b) (c d) S {fields}\n") == "220"


def test_the_start_stamp_is_the_same_under_any_locale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    process = spawn(
        ["sleep", SLEEP_SECONDS],
        pid_file=tmp_path / "locale.pid",
        log_file=tmp_path / "locale.log",
    )
    try:
        monkeypatch.setenv("LC_ALL", "C")
        first = _start_stamp(process.pid)
        monkeypatch.setenv("LC_ALL", "de_DE.UTF-8")
        monkeypatch.setenv("LC_TIME", "de_DE.UTF-8")
        assert first
        assert _start_stamp(process.pid) == first
    finally:
        process.kill()
        process.wait()


def test_pid_alive_reads_the_pid_file_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid_file = tmp_path / "once.pid"
    pid_file.write_text("999999\nstamp")
    reads: list[Path] = []
    original = Path.read_text

    def counting_read_text(self: Path, *args: object, **kwargs: object) -> str:
        reads.append(self)
        return original(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "read_text", counting_read_text)
    assert not pid_alive(pid_file)
    assert reads.count(pid_file) == 1


def test_a_pid_file_of_a_non_leader_process_is_not_ours(tmp_path: Path) -> None:
    bystander = subprocess.Popen(["sleep", SLEEP_SECONDS])
    try:
        pid_file = tmp_path / "bystander.pid"
        pid_file.write_text(f"{bystander.pid}\n{_stamp(bystander.pid)}")
        assert not pid_alive(pid_file)
        assert not pid_file.exists()
        pid_file.write_text(f"{bystander.pid}\n{_stamp(bystander.pid)}")
        terminate(pid_file, timeout_s=SHORT_TIMEOUT_S)
        assert bystander.poll() is None
    finally:
        bystander.kill()
        bystander.wait()


def test_a_pid_file_with_a_different_start_time_is_not_ours(tmp_path: Path) -> None:
    pid_file = tmp_path / "reused.pid"
    process = spawn(
        ["sleep", SLEEP_SECONDS], pid_file=pid_file, log_file=tmp_path / "r.log"
    )
    try:
        pid_file.write_text(f"{process.pid}\nMon Jan  1 00:00:00 2001")
        assert not pid_alive(pid_file)
        assert process.poll() is None
    finally:
        process.kill()
        process.wait()


def test_pid_alive_is_false_for_a_finished_process(tmp_path: Path) -> None:
    finished = subprocess.Popen(["true"])
    finished.wait()
    pid_file = tmp_path / "gone.pid"
    pid_file.write_text(f"{finished.pid}\nrecorded start")
    assert not pid_alive(pid_file)
    assert not pid_alive(tmp_path / "missing.pid")
