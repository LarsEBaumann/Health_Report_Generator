"""Own a local worker session and reconcile interrupted database state."""

from contextlib import contextmanager

from worker_lock import worker_lock


def lock_path_for(store):
    """All workers for this database must use this same persistent path."""
    return store.path.resolve().with_name(store.path.name + ".worker.lock")


@contextmanager
def worker_session(store):
    """Keep ownership for the whole session, not just startup recovery."""
    with worker_lock(lock_path_for(store)) as lock_fd:
        interrupted = store.fail_interrupted()
        yield {
            "lock_fd": lock_fd,
            "interrupted_job_ids": interrupted,
        }
