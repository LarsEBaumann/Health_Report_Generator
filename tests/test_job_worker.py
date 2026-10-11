import json
from pathlib import Path

import pytest

from job_store import JobStore
from job_worker import run_one
from report_publication import read_publication
from worker_session import worker_session


@pytest.fixture
def environment(tmp_path):
    store = JobStore(tmp_path / "state" / "jobs.sqlite3")
    store.initialize()
    renderer = tmp_path / "renderer.py"
    renderer.write_text("""
import argparse
import json
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("request")
parser.add_argument("--out")
parser.add_argument("--data-root")
parser.add_argument("--cache")
args = parser.parse_args()
settings = json.loads(Path(args.request).read_text())
mode = settings.get("fixture_mode", "success")
if mode == "timeout":
    time.sleep(10)
if mode == "failure":
    raise SystemExit("PRIVATE_DIAGNOSTIC")
out = Path(args.out)
out.mkdir()
if mode == "invalid":
    (out / "report.html").write_text("incomplete")
else:
    (out / "report.html").write_text('<a href="methods.html">Methods</a>')
    (out / "methods.html").write_text("<html>Methods</html>")
    (out / "provenance.json").write_text(json.dumps({
        "effective_parameters": {
            **settings, "id": "custom_0123456789ab",
        }
    }))
    (out / "request_provenance.json").write_text(
        json.dumps({"cache_key": "a" * 64})
    )
""")
    options = {
        "workspace_root": tmp_path / "private",
        "published_root": tmp_path / "published",
        "data_root": tmp_path / "data",
        "cache_root": tmp_path / "cache",
        "cwd": tmp_path,
        "renderer": renderer,
        "timeout": 3,
        "grace": 0.05,
    }
    return store, options


def submit(store, mode="success", key="a" * 64):
    return store.submit(
        key, {"id": "public", "years": [2022, 2025], "fixture_mode": mode}
    )[0]


def test_success_publishes_and_persists(environment):
    store, options = environment
    job = submit(store)
    result = run_one(store, **options)
    assert result["state"] == "completed"
    assert result["error_code"] is None
    published = options["published_root"] / job["job_id"]
    read_publication(published, job["job_id"], "a" * 64, job["request"])
    assert JobStore(store.path).get(job["job_id"])["state"] == "completed"
    workspace = options["workspace_root"] / job["job_id"]
    assert json.loads((workspace / "request.json").read_text()) == job["request"]
    assert (workspace / "render.log").exists()
    assert not (published / "render.log").exists()


@pytest.mark.parametrize("mode,code", [
    ("failure", "RENDER_FAILED"),
    ("timeout", "RENDER_TIMEOUT"),
    ("invalid", "REPORT_INVALID"),
])
def test_render_failures_are_sanitized(environment, mode, code):
    store, options = environment
    job = submit(store, mode)
    if mode == "timeout":
        options["timeout"] = 0.2
    result = run_one(store, **options)
    assert result["state"] == "failed"
    assert result["error_code"] == code
    assert "PRIVATE_DIAGNOSTIC" not in json.dumps(result)
    assert not (options["published_root"] / job["job_id"]).exists()


def test_empty_queue_does_not_start_renderer(environment):
    store, options = environment
    assert run_one(store, **options) is None
    assert not options["workspace_root"].exists()


def test_only_one_job_is_processed(environment):
    store, options = environment
    first = submit(store, key="a" * 64)
    second = submit(store, key="b" * 64)
    assert run_one(store, **options)["job_id"] == first["job_id"]
    assert store.get(second["job_id"])["state"] == "queued"


def test_publication_survives_completion_persistence_failure(
    environment, monkeypatch
):
    store, options = environment
    job = submit(store)

    def unavailable(*args, **kwargs):
        raise RuntimeError("simulated persistence failure")

    with monkeypatch.context() as patch:
        patch.setattr(store, "finish", unavailable)
        with pytest.raises(RuntimeError, match="persistence failure"):
            run_one(store, **options)

    assert store.get(job["job_id"])["state"] == "running"
    with worker_session(store, options["published_root"]) as session:
        assert session["recovered_job_ids"] == [job["job_id"]]
    assert store.get(job["job_id"])["state"] == "completed"


def test_invalid_budget_does_not_claim_job(environment):
    store, options = environment
    job = submit(store)
    options["timeout"] = 0
    with pytest.raises(ValueError):
        run_one(store, **options)
    assert store.get(job["job_id"])["state"] == "queued"


def test_worker_rejects_rendered_identity_mismatch(environment):
    store, options = environment
    job = submit(store, key="b" * 64)
    result = run_one(store, **options)
    assert result["state"] == "failed"
    assert result["error_code"] == "PUBLICATION_INVALID"
    assert not (options["published_root"] / job["job_id"]).exists()
    assert (
        options["workspace_root"] / job["job_id"] / "report"
        / "request_provenance.json"
    ).exists()
