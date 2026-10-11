import stat
import sys

import pytest

from process_supervisor import run_supervised
from worker_lock import worker_lock


def run(tmp_path, code, *, timeout=5):
    with worker_lock(tmp_path / "worker.lock") as fd:
        return run_supervised(
            [sys.executable, "-c", code],
            cwd=tmp_path,
            log_path=tmp_path / "private.log",
            lock_fd=fd,
            timeout=timeout,
            grace=0.1,
        )


def test_success_and_private_log(tmp_path):
    result = run(tmp_path, "print('finished')")
    assert result.returncode == 0
    assert not result.timed_out
    log = tmp_path / "private.log"
    assert "finished" in log.read_text()
    assert stat.S_IMODE(log.stat().st_mode) == 0o600


def test_nonzero_exit_is_preserved(tmp_path):
    result = run(tmp_path, "import sys; sys.exit(7)")
    assert result.returncode == 7
    assert not result.timed_out


def test_timeout_terminates_direct_process(tmp_path):
    result = run(tmp_path, "import time; time.sleep(30)", timeout=0.3)
    assert result.timed_out
    assert result.returncode != 0


def test_ownership_descriptor_is_passed(tmp_path):
    with worker_lock(tmp_path / "worker.lock") as fd:
        result = run_supervised(
            [sys.executable, "-c", f"import os; os.fstat({fd}); print('held')"],
            cwd=tmp_path,
            log_path=tmp_path / "private.log",
            lock_fd=fd,
            grace=0.1,
        )
    assert result.returncode == 0
    assert "held" in (tmp_path / "private.log").read_text()


def test_argument_is_not_shell_interpreted(tmp_path):
    marker = tmp_path / "should-not-exist"
    argument = f"; touch {marker}"
    with worker_lock(tmp_path / "worker.lock") as fd:
        result = run_supervised(
            [sys.executable, "-c", "import sys; print(sys.argv[1])", argument],
            cwd=tmp_path,
            log_path=tmp_path / "private.log",
            lock_fd=fd,
            grace=0.1,
        )
    assert result.returncode == 0
    assert not marker.exists()
    assert argument in (tmp_path / "private.log").read_text()


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), True])
def test_invalid_timeout_is_rejected(tmp_path, timeout):
    with worker_lock(tmp_path / "worker.lock") as fd:
        with pytest.raises(ValueError):
            run_supervised(
                [sys.executable, "-c", "pass"],
                cwd=tmp_path,
                log_path=tmp_path / "private.log",
                lock_fd=fd,
                timeout=timeout,
            )


def test_existing_log_is_not_overwritten(tmp_path):
    log = tmp_path / "private.log"
    log.write_text("preserve")
    with worker_lock(tmp_path / "worker.lock") as fd:
        with pytest.raises(FileExistsError):
            run_supervised(
                [sys.executable, "-c", "pass"],
                cwd=tmp_path,
                log_path=log,
                lock_fd=fd,
            )
    assert log.read_text() == "preserve"


def test_invalid_descriptor_is_rejected(tmp_path):
    with pytest.raises(OSError):
        run_supervised(
            [sys.executable, "-c", "pass"],
            cwd=tmp_path,
            log_path=tmp_path / "private.log",
            lock_fd=-1,
        )
    assert not (tmp_path / "private.log").exists()
