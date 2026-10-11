import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from report_bundle import BundleInvalid
from report_publication import (
    PublicationConflict,
    publish_bundle,
    read_publication,
)

JOB_ID = "1" * 32
KEY = "a" * 64


@pytest.fixture
def setup(tmp_path):
    source = tmp_path / "private"
    source.mkdir()
    settings = {"id": "public", "years": [2022, 2025]}
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
    return source, tmp_path / "published", settings


def test_publication_and_independent_read(setup):
    source, root, settings = setup
    destination = publish_bundle(source, root, JOB_ID, KEY, settings)
    assert destination == root / JOB_ID
    assert source.exists()
    record = read_publication(destination, JOB_ID, KEY, settings)
    assert len(record["files"]) == 4
    assert list((root / ".staging").iterdir()) == []


def test_repeat_publication_is_idempotent(setup):
    source, root, settings = setup
    first = publish_bundle(source, root, JOB_ID, KEY, settings)
    before = (first / "publication.json").read_bytes()
    second = publish_bundle(source, root, JOB_ID, KEY, settings)
    assert first == second
    assert (second / "publication.json").read_bytes() == before


def test_invalid_bundle_is_not_published(setup):
    source, root, settings = setup
    (source / "methods.html").unlink()
    with pytest.raises(BundleInvalid):
        publish_bundle(source, root, JOB_ID, KEY, settings)
    assert not (root / JOB_ID).exists()


def test_existing_directory_is_not_overwritten(setup):
    source, root, settings = setup
    destination = root / JOB_ID
    destination.mkdir(parents=True)
    with pytest.raises(PublicationConflict):
        publish_bundle(source, root, JOB_ID, KEY, settings)
    assert list(destination.iterdir()) == []


def test_tampering_is_detected(setup):
    source, root, settings = setup
    destination = publish_bundle(source, root, JOB_ID, KEY, settings)
    (destination / "methods.html").write_text("tampered")
    with pytest.raises(PublicationConflict):
        read_publication(destination, JOB_ID, KEY, settings)


def test_identity_conflict_is_rejected(setup):
    source, root, settings = setup
    publish_bundle(source, root, JOB_ID, KEY, settings)
    with pytest.raises(PublicationConflict):
        publish_bundle(source, root, JOB_ID, "b" * 64, settings)


@pytest.mark.parametrize("job_id", ["../outside", "", "x" * 32])
def test_unsafe_job_id_is_rejected(setup, job_id):
    source, root, settings = setup
    with pytest.raises(ValueError):
        publish_bundle(source, root, job_id, KEY, settings)


def test_concurrent_publication_is_serialized(setup):
    source, root, settings = setup

    def attempt(_):
        try:
            return publish_bundle(source, root, JOB_ID, KEY, settings)
        except RuntimeError:
            # Nonblocking ownership rejects a competing publisher.
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, range(2)))
    assert any(result == root / JOB_ID for result in results)
    read_publication(root / JOB_ID, JOB_ID, KEY, settings)


def test_rendered_identity_mismatch_is_not_published(setup):
    source, root, settings = setup
    with pytest.raises(PublicationConflict):
        publish_bundle(source, root, JOB_ID, "b" * 64, settings)
    assert not root.exists()


def test_matching_manifest_identity_cannot_hide_rendered_mismatch(setup):
    source, root, settings = setup
    destination = publish_bundle(source, root, JOB_ID, KEY, settings)
    marker_path = destination / "publication.json"
    marker = json.loads(marker_path.read_text())
    marker["request_key"] = "b" * 64
    marker_path.write_text(json.dumps(marker))
    with pytest.raises(PublicationConflict):
        read_publication(destination, JOB_ID, "b" * 64, settings)


@pytest.mark.parametrize("key", ["", "internal-key", "x" * 64, "A" * 64])
def test_invalid_publication_request_key_is_rejected(setup, key):
    source, root, settings = setup
    with pytest.raises(ValueError):
        publish_bundle(source, root, JOB_ID, key, settings)
    assert not root.exists()
