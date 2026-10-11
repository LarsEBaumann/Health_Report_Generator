"""Own a local worker session and reconcile interrupted database state."""

from contextlib import contextmanager
from pathlib import Path

from report_publication import PublicationConflict, read_publication
from worker_lock import worker_lock


def lock_path_for(store):
    """All workers for this database must use this same persistent path."""
    return store.path.resolve().with_name(store.path.name + ".worker.lock")


@contextmanager
def worker_session(store, published_root=None):
    """Keep ownership for recovery and the entire subsequent worker session."""
    with worker_lock(lock_path_for(store)) as lock_fd:
        recovered = []
        invalid = []
        interrupted = []

        if published_root is None:
            interrupted = store.fail_interrupted()
        else:
            root = Path(published_root)
            if root.is_symlink():
                raise PublicationConflict("Publication root cannot be a symlink.")

            for job in store.running_jobs():
                destination = root / job["job_id"]
                if not destination.exists() and not destination.is_symlink():
                    store.finish(job["job_id"], "failed", "WORKER_INTERRUPTED")
                    interrupted.append(job["job_id"])
                    continue

                try:
                    read_publication(
                        destination,
                        job["job_id"],
                        job["request_key"],
                        job["request"],
                    )
                except PublicationConflict:
                    store.finish(job["job_id"], "failed", "PUBLICATION_INVALID")
                    invalid.append(job["job_id"])
                else:
                    store.finish(job["job_id"], "completed")
                    recovered.append(job["job_id"])

        yield {
            "lock_fd": lock_fd,
            "interrupted_job_ids": interrupted,
            "recovered_job_ids": recovered,
            "invalid_publication_job_ids": invalid,
        }
