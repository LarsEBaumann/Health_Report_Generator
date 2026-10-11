import json
import shutil

import pytest

from job_store import JobStore
from report_publication import publish_bundle
from worker_session import worker_session


@pytest.fixture
def setup(tmp_path):
    store = JobStore(tmp_path / "state" / "jobs.sqlite3")
    store.initialize()
    settings = {"id": "public", "years": [2022, 2025]}
    source = tmp_path / "private"
    source.mkdir()
    (source / "report.html").write_text('<a href="methods.html">Methods</a>')
    (source / "methods.html").write_text("<html>Methods</html>")
    (source / "provenance.json").write_text(json.dumps({
        "effective_parameters": {
            **settings, "id": "custom_0123456789ab",
        }
    }))
    (source / "request_provenance.json").write_text(
        json.dumps({"cache_key": "a" * 64})
    )
    return store, source, tmp_path / "published", settings


def test_published_running_job_recovers_without_source(setup):
    store, source, root, settings = setup
    job, _ = store.submit("key", settings)
    store.claim_next()
    destination = publish_bundle(source, root, job["job_id"], "key", settings)

    # Simulate interruption before finish(); private workspace is unavailable.
    shutil.rmtree(source)
    reopened = JobStore(store.path)
    with worker_session(reopened, root) as session:
        assert session["recovered_job_ids"] == [job["job_id"]]
        assert reopened.get(job["job_id"])["state"] == "completed"

    assert destination.exists()
    before = reopened.get(job["job_id"])
    with worker_session(reopened, root) as session:
        assert session["recovered_job_ids"] == []
    assert reopened.get(job["job_id"]) == before


def test_missing_publication_fails_without_discarding_queue(setup):
    store, source, root, settings = setup
    interrupted, _ = store.submit("first", settings)
    store.claim_next()
    waiting, _ = store.submit("second", settings)

    with worker_session(store, root) as session:
        assert session["interrupted_job_ids"] == [interrupted["job_id"]]
        assert store.get(interrupted["job_id"])["error_code"] == (
            "WORKER_INTERRUPTED"
        )
        assert store.get(waiting["job_id"])["state"] == "queued"


def test_invalid_publication_is_preserved_but_not_completed(setup):
    store, source, root, settings = setup
    job, _ = store.submit("key", settings)
    store.claim_next()
    destination = publish_bundle(source, root, job["job_id"], "key", settings)
    (destination / "methods.html").write_text("tampered")

    with worker_session(store, root) as session:
        assert session["invalid_publication_job_ids"] == [job["job_id"]]
        record = store.get(job["job_id"])
        assert record["state"] == "failed"
        assert record["error_code"] == "PUBLICATION_INVALID"

    assert (destination / "methods.html").read_text() == "tampered"


def test_existing_completed_job_is_untouched(setup):
    store, source, root, settings = setup
    job, _ = store.submit("key", settings)
    store.claim_next()
    publish_bundle(source, root, job["job_id"], "key", settings)
    store.finish(job["job_id"], "completed")
    before = store.get(job["job_id"])

    with worker_session(store, root) as session:
        assert session["recovered_job_ids"] == []
        assert session["interrupted_job_ids"] == []

    assert store.get(job["job_id"]) == before
