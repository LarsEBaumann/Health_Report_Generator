import pytest

from job_store import JobStore, QueueFull
from worker_lock import WorkerAlreadyRunning, worker_lock
from worker_session import lock_path_for, worker_session


@pytest.fixture
def store(tmp_path):
    result = JobStore(tmp_path / "jobs.sqlite3")
    result.initialize()
    return result


def test_interrupted_running_job_fails_but_queue_survives(store):
    interrupted, _ = store.submit("interrupted", {})
    store.claim_next()
    waiting, _ = store.submit("waiting", {})

    reopened = JobStore(store.path)
    with worker_session(reopened) as session:
        assert session["interrupted_job_ids"] == [interrupted["job_id"]]
        assert reopened.get(interrupted["job_id"])["state"] == "failed"
        assert reopened.get(interrupted["job_id"])["error_code"] == (
            "WORKER_INTERRUPTED"
        )
        assert reopened.get(waiting["job_id"])["state"] == "queued"
        assert reopened.claim_next()["job_id"] == waiting["job_id"]


def test_completed_job_is_unchanged(store):
    job, _ = store.submit("completed", {})
    store.claim_next()
    store.finish(job["job_id"], "completed")
    before = store.get(job["job_id"])

    with worker_session(store) as session:
        assert session["interrupted_job_ids"] == []
        assert store.get(job["job_id"]) == before


def test_existing_owner_blocks_reconciliation(store):
    job, _ = store.submit("running", {})
    store.claim_next()

    with worker_lock(lock_path_for(store)):
        with pytest.raises(WorkerAlreadyRunning):
            with worker_session(store):
                pytest.fail("Second worker acquired ownership.")

    assert store.get(job["job_id"])["state"] == "running"


def test_session_holds_ownership_until_exit(store):
    with worker_session(store):
        with pytest.raises(WorkerAlreadyRunning):
            with worker_session(store):
                pytest.fail("Nested worker acquired ownership.")

    with worker_session(store) as session:
        assert session["interrupted_job_ids"] == []


def test_recovery_does_not_overfill_or_discard_queue(store):
    interrupted, _ = store.submit("interrupted", {})
    store.claim_next()
    waiting_ids = []
    for number in range(20):
        job, _ = store.submit(f"waiting-{number}", {"test": number})
        waiting_ids.append(job["job_id"])

    with worker_session(store):
        assert store.get(interrupted["job_id"])["state"] == "failed"
        assert all(store.get(job_id)["state"] == "queued"
                   for job_id in waiting_ids)
        with pytest.raises(QueueFull):
            store.submit("overflow", {})


def test_reconciliation_is_idempotent(store):
    job, _ = store.submit("interrupted", {})
    store.claim_next()

    with worker_session(store) as first:
        assert first["interrupted_job_ids"] == [job["job_id"]]
    before = store.get(job["job_id"])

    with worker_session(store) as second:
        assert second["interrupted_job_ids"] == []
    assert store.get(job["job_id"]) == before
