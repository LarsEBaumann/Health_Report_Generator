import subprocess
import sys

import pytest

from worker_lock import WorkerAlreadyRunning, worker_lock


PROBE = """
import fcntl
import sys

with open(sys.argv[1], "a+b") as handle:
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit(10)
"""


def probe(path):
    return subprocess.run(
        [sys.executable, "-c", PROBE, str(path)],
        check=False,
        timeout=10,
    ).returncode


def test_second_owner_is_rejected(tmp_path):
    path = tmp_path / "worker.lock"
    with worker_lock(path):
        with pytest.raises(WorkerAlreadyRunning):
            with worker_lock(path):
                pytest.fail("Second owner acquired the lock.")
        assert probe(path) == 10
    assert probe(path) == 0
    assert path.exists()


def test_exception_releases_owner(tmp_path):
    path = tmp_path / "worker.lock"
    with pytest.raises(RuntimeError, match="test failure"):
        with worker_lock(path):
            raise RuntimeError("test failure")
    assert probe(path) == 0


def test_process_death_releases_owner(tmp_path):
    path = tmp_path / "worker.lock"
    child = subprocess.Popen(
        [
            sys.executable,
            "-u",
            "-c",
            """
import fcntl
import sys
import time

handle = open(sys.argv[1], "a+b")
fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
print("LOCKED", flush=True)
time.sleep(30)
""",
            str(path),
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert child.stdout.readline().strip() == "LOCKED"
        assert probe(path) == 10
        child.kill()
        child.wait(timeout=10)
        assert probe(path) == 0
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=10)
        child.stdout.close()
