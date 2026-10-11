from concurrent.futures import ThreadPoolExecutor

import pytest

from job_store import InvalidTransition, JobStore, QueueFull


@pytest.fixture
def store(tmp_path):
    result = JobStore(tmp_path / "state" / "jobs.sqlite3")
    result.initialize()
    return result


def test_persistence_and_initialize_is_idempotent(store):
    job, created = store.submit("internal-key", {"audience": "public"})
    assert created
    reopened = JobStore(store.path)
    reopened.initialize()
    assert reopened.get(job["job_id"])["request"] == {"audience": "public"}
    assert reopened.get("missing") is None


def test_duplicate_can_join_a_full_queue(store):
    original, _ = store.submit("key-0", {"test": 0})
    for number in range(1, 20):
        store.submit(f"key-{number}", {"test": number})
    same, created = store.submit("key-0", {"test": 0})
    assert not created
    assert same["job_id"] == original["job_id"]
    with pytest.raises(QueueFull):
        store.submit("overflow", {"test": 20})


def test_fifo_and_only_one_running(store):
    first, _ = store.submit("first", {})
    second, _ = store.submit("second", {})
    assert store.claim_next()["job_id"] == first["job_id"]
    assert store.claim_next() is None
    store.finish(first["job_id"], "completed")
    assert store.claim_next()["job_id"] == second["job_id"]


def test_twenty_waiting_plus_one_running(store):
    active, _ = store.submit("active", {})
    assert store.claim_next()["job_id"] == active["job_id"]
    for number in range(20):
        store.submit(f"waiting-{number}", {"test": number})
    with pytest.raises(QueueFull):
        store.submit("overflow", {})


def test_transitions_and_sanitized_errors(store):
    job, _ = store.submit("request", {})
    with pytest.raises(InvalidTransition):
        store.finish(job["job_id"], "completed")
    store.claim_next()
    with pytest.raises(ValueError):
        store.finish(job["job_id"], "failed", "/private/path traceback")
    store.finish(job["job_id"], "failed", "RENDER_FAILED")
    assert store.get(job["job_id"])["error_code"] == "RENDER_FAILED"
    with pytest.raises(InvalidTransition):
        store.finish(job["job_id"], "completed")
    replacement, created = store.submit("request", {})
    assert created
    assert replacement["job_id"] != job["job_id"]


def test_identity_conflict_is_rejected(store):
    store.submit("same-key", {"test": 1})
    with pytest.raises(ValueError):
        store.submit("same-key", {"test": 2})


def test_concurrent_duplicate_submissions(store):
    def submit(_):
        return store.submit("shared-key", {"test": 1})

    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(submit, range(20)))
    assert sum(created for _, created in results) == 1
    assert len({job["job_id"] for job, _ in results}) == 1


def test_concurrent_admission_respects_limit(store):
    def submit(number):
        try:
            store.submit(f"unique-{number}", {"test": number})
            return True
        except QueueFull:
            return False

    with ThreadPoolExecutor(max_workers=20) as pool:
        accepted = list(pool.map(submit, range(30)))
    assert sum(accepted) == 20


def test_concurrent_claims_have_one_winner(store):
    for number in range(5):
        store.submit(f"key-{number}", {"test": number})

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(lambda _: store.claim_next(), range(10)))
    assert sum(result is not None for result in results) == 1
