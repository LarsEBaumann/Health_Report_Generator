"""Bounded execution of trusted internal commands on Linux."""

import math
import os
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    timed_out: bool


def _signal_group(pid, sig):
    try:
        os.killpg(pid, sig)
        return True
    except ProcessLookupError:
        return False


def _cleanup_group(process, grace):
    # Clean descendants even if the direct child has already exited.
    if _signal_group(process.pid, signal.SIGTERM):
        time.sleep(grace)
        _signal_group(process.pid, signal.SIGKILL)
    process.wait()


def run_supervised(argv, *, cwd, log_path, lock_fd, timeout=300, grace=1):
    """Run trusted arguments; caller retains worker ownership throughout."""
    if (
        type(argv) is not list
        or not argv
        or any(type(arg) is not str or not arg for arg in argv)
    ):
        raise ValueError("Command must be a non-empty list of strings.")

    for name, value in (("timeout", timeout), ("grace", grace)):
        if (
            type(value) not in (int, float)
            or not math.isfinite(value)
            or value <= 0
        ):
            raise ValueError(f"{name} must be positive and finite.")

    os.fstat(lock_fd)
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    fd = os.open(
        log_path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    with os.fdopen(fd, "wb") as log:
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            shell=False,
            start_new_session=True,
            pass_fds=(lock_fd,),
        )
        timed_out = False
        try:
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
        finally:
            _cleanup_group(process, grace)

    return ProcessResult(
        returncode=process.returncode,
        timed_out=timed_out,
    )
