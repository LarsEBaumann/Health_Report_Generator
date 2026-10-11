import os
import signal
import subprocess
import sys
import time

import psutil
import pytest

from process_supervisor import run_supervised
from worker_lock import WorkerAlreadyRunning, worker_lock


def alive(pid):
    try:
        process = psutil.Process(pid)
        return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False


def wait_stopped(pid):
    deadline = time.monotonic() + 5
    while alive(pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not alive(pid), f"Process {pid} is still running."


@pytest.mark.parametrize("parent_sleeps", [True, False])
def test_descendant_is_cleaned_up(tmp_path, parent_sleeps):
    pid_file = tmp_path / "descendant.pid"
    child_code = """
import os
import signal
import time
from pathlib import Path
import sys

signal.signal(signal.SIGTERM, signal.SIG_IGN)
Path(sys.argv[1]).write_text(str(os.getpid()))
time.sleep(30)
"""
    parent_code = f"""
import subprocess
import sys
import time
from pathlib import Path

subprocess.Popen([sys.executable, "-c", {child_code!r}, {str(pid_file)!r}])
deadline = time.monotonic() + 5
while not Path({str(pid_file)!r}).exists():
    if time.monotonic() > deadline:
        raise RuntimeError("Child did not start")
    time.sleep(0.01)
if {parent_sleeps!r}:
    time.sleep(30)
"""
    descendant_pid = None
    try:
        with worker_lock(tmp_path / "worker.lock") as fd:
            result = run_supervised(
                [sys.executable, "-c", parent_code],
                cwd=tmp_path,
                log_path=tmp_path / "private.log",
                lock_fd=fd,
                timeout=2,
                grace=0.1,
            )

        assert pid_file.exists()
        descendant_pid = int(pid_file.read_text())
        wait_stopped(descendant_pid)
        assert result.timed_out == parent_sleeps
        if not parent_sleeps:
            assert result.returncode == 0
    finally:
        if descendant_pid is None and pid_file.exists():
            descendant_pid = int(pid_file.read_text())
        if descendant_pid is not None and alive(descendant_pid):
            try:
                os.kill(descendant_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def test_child_retains_lock_after_parent_descriptor_closes(tmp_path):
    path = tmp_path / "worker.lock"
    child = None
    try:
        with worker_lock(path) as fd:
            child = subprocess.Popen(
                [
                    sys.executable,
                    "-u",
                    "-c",
                    f"""
import os
import time
os.fstat({fd})
print("READY", flush=True)
time.sleep(30)
""",
                ],
                pass_fds=(fd,),
                stdout=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
            assert child.stdout.readline().strip() == "READY"

        # Parent ownership descriptor has closed; the child still holds it.
        with pytest.raises(WorkerAlreadyRunning):
            with worker_lock(path):
                pytest.fail("Ownership was acquired while child still held it.")

        child.kill()
        child.wait(timeout=5)

        with worker_lock(path):
            pass
    finally:
        if child is not None:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)
            child.stdout.close()
