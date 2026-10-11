"""Cooperative single-host worker ownership on a persistent local file."""

import fcntl
from contextlib import contextmanager
from pathlib import Path


class WorkerAlreadyRunning(RuntimeError):
    """Another cooperating process holds this worker lock."""


@contextmanager
def worker_lock(path):
    """Hold ownership; never unlink the lock file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise WorkerAlreadyRunning("Worker ownership is already held.") from exc
        yield handle.fileno()
    finally:
        # Close rather than explicitly unlock: inherited descriptors, when
        # deliberately passed to children, must retain their ownership.
        handle.close()
