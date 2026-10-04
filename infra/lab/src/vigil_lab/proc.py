from __future__ import annotations

import contextlib
import os
import shlex
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

ERROR_TAIL_CHARS = 2000
POLL_INTERVAL_S = 2.0
SSH_PROBE_TIMEOUT_S = 15.0
TERMINATE_TIMEOUT_S = 30.0
SIGNAL_POLL_INTERVAL_S = 0.5
STAT_STARTTIME_INDEX = 19


class LabError(RuntimeError):
    pass


def run(
    args: Sequence[str],
    *,
    env: Mapping[str, str] | None = None,
    input_text: str | None = None,
    log_file: Path | None = None,
) -> str:
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
    with (
        log_file.open("a")
        if log_file
        else contextlib.nullcontext(subprocess.PIPE) as stderr
    ):
        result = subprocess.run(
            list(args),
            env=env,
            input=input_text,
            stdout=subprocess.PIPE,
            stderr=stderr,
            text=True,
            check=False,
        )
    if result.returncode != 0:
        detail = (
            f"see {log_file}" if log_file else result.stderr.strip()[-ERROR_TAIL_CHARS:]
        )
        raise LabError(f"{shlex.join(args)} exited {result.returncode}: {detail}")
    return result.stdout


def probe(args: Sequence[str], timeout_s: float) -> bool:
    try:
        result = subprocess.run(
            list(args), capture_output=True, timeout=timeout_s, check=False
        )
    except subprocess.TimeoutExpired:
        return False
    return result.returncode == 0


def spawn(
    args: Sequence[str],
    *,
    pid_file: Path,
    log_file: Path,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> subprocess.Popen[bytes]:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("ab") as log:
        process = subprocess.Popen(
            list(args),
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            cwd=cwd,
            env=env,
            start_new_session=True,
        )
    pid_file.write_text(f"{process.pid}\n{_start_stamp(process.pid)}")
    return process


def stat_start_ticks(stat_text: str) -> str:
    return stat_text.rpartition(")")[2].split()[STAT_STARTTIME_INDEX]


def _start_stamp(pid: int) -> str:
    try:
        if sys.platform.startswith("linux"):
            return stat_start_ticks(Path(f"/proc/{pid}/stat").read_text())
        return run(
            ["ps", "-o", "lstart=", "-p", str(pid)],
            env={**os.environ, "LC_ALL": "C"},
        ).strip()
    except (LabError, OSError, IndexError):
        return ""


def _parse_pid_file(text: str) -> tuple[int, list[str]] | None:
    lines = text.splitlines()
    try:
        return int(lines[0]), lines[1:]
    except (ValueError, IndexError):
        return None


def _verified_pid(pid_file: Path) -> int | None:
    try:
        parsed = _parse_pid_file(pid_file.read_text())
    except FileNotFoundError:
        return None
    if parsed is None:
        return None
    pid, recorded = parsed
    try:
        if os.getpgid(pid) != pid:
            return None
    except (ProcessLookupError, PermissionError):
        return None
    stamp = _start_stamp(pid)
    if not stamp or recorded != [stamp]:
        return None
    with contextlib.suppress(ChildProcessError):
        if os.waitpid(pid, os.WNOHANG)[0] == pid:
            return None
    return pid


def pid_alive(pid_file: Path) -> bool:
    if _verified_pid(pid_file) is not None:
        return True
    pid_file.unlink(missing_ok=True)
    return False


def terminate(pid_file: Path, timeout_s: float = TERMINATE_TIMEOUT_S) -> None:
    pid = _verified_pid(pid_file)
    if pid is not None:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(pid, signal.SIGTERM)
        deadline = time.monotonic() + timeout_s
        while _verified_pid(pid_file) is not None and time.monotonic() < deadline:
            time.sleep(SIGNAL_POLL_INTERVAL_S)
        if _verified_pid(pid_file) is not None:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(pid, signal.SIGKILL)
    pid_file.unlink(missing_ok=True)


def wait_until(
    check: Callable[[], bool],
    timeout_s: float,
    description: str,
    interval_s: float = POLL_INTERVAL_S,
) -> None:
    deadline = time.monotonic() + timeout_s
    while not check():
        if time.monotonic() > deadline:
            raise LabError(
                f"timed out after {timeout_s:.0f} s waiting for {description}"
            )
        time.sleep(interval_s)
