from __future__ import annotations

import contextlib
import shlex
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

ERROR_TAIL_CHARS = 2000
POLL_INTERVAL_S = 2.0


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
