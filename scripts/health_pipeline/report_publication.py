"""Verified publication on a trusted local filesystem."""

import json
import os
import re
import shutil
import tempfile
from pathlib import Path

from report_bundle import BundleInvalid, verify_bundle
from worker_lock import worker_lock

MANIFEST = "publication.json"


class PublicationConflict(ValueError):
    """Existing output does not match the requested publication."""


def _identity(job_id, request_key):
    if type(job_id) is not str or not re.fullmatch(r"[a-f0-9]{32}", job_id):
        raise ValueError("Invalid internal job identifier.")
    if (
        type(request_key) is not str
        or not re.fullmatch(r"[a-f0-9]{64}", request_key)
    ):
        raise ValueError("Invalid renderer-derived request identity.")


def _sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _sync_tree(root):
    directories = [root]
    for path in root.rglob("*"):
        if path.is_dir():
            directories.append(path)
        elif path.is_file():
            with path.open("rb") as handle:
                os.fsync(handle.fileno())
    for path in sorted(directories, key=lambda p: len(p.parts), reverse=True):
        _sync_directory(path)


def read_publication(directory, job_id, request_key, expected_settings):
    """Verify a published artifact; do not alter job state or files."""
    _identity(job_id, request_key)
    directory = Path(directory)
    try:
        if directory.is_symlink() or (directory / MANIFEST).is_symlink():
            raise PublicationConflict("Published output cannot be a symlink.")
        marker = json.loads((directory / MANIFEST).read_text())
        if (
            type(marker) is not dict
            or marker.get("schema") != "sourceprism-publication/1"
            or marker.get("job_id") != job_id
            or marker.get("request_key") != request_key
            or marker.get("settings") != expected_settings
        ):
            raise PublicationConflict("Publication identity differs.")
        verified = verify_bundle(directory, expected_settings)
        verified["files"].pop(MANIFEST, None)
        if (
            marker.get("cache_key") != verified["cache_key"]
            or verified["cache_key"] != request_key
            or marker.get("files") != verified["files"]
        ):
            raise PublicationConflict("Published inventory differs.")
        return marker
    except (OSError, UnicodeError, json.JSONDecodeError, BundleInvalid) as exc:
        raise PublicationConflict("Published output failed verification.") from exc


def publish_bundle(source, published_root, job_id, request_key, settings):
    """Copy, verify and publish; all publishers must share this root lock."""
    _identity(job_id, request_key)
    source = Path(source)
    if (source / MANIFEST).exists():
        raise PublicationConflict("Source already contains publication metadata.")
    initial = verify_bundle(source, settings)
    if initial["cache_key"] != request_key:
        raise PublicationConflict("Rendered identity differs from queued identity.")

    root = Path(published_root)
    if root.is_symlink():
        raise PublicationConflict("Publication root cannot be a symlink.")
    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve()
    destination = root / job_id

    expected = {
        "schema": "sourceprism-publication/1",
        "job_id": job_id,
        "request_key": request_key,
        "settings": settings,
        "cache_key": initial["cache_key"],
        "files": initial["files"],
    }

    with worker_lock(root / ".publication.lock"):
        if destination.exists() or destination.is_symlink():
            existing = read_publication(
                destination, job_id, request_key, settings
            )
            if existing != expected:
                raise PublicationConflict("Existing artifact differs.")
            return destination

        staging_root = root / ".staging"
        if staging_root.is_symlink():
            raise PublicationConflict("Staging root cannot be a symlink.")
        staging_root.mkdir(exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=f"{job_id}-", dir=staging_root))
        try:
            shutil.copytree(source, stage, dirs_exist_ok=True, symlinks=True)
            copied = verify_bundle(stage, settings)
            if copied != initial:
                raise PublicationConflict("Source changed during copying.")

            marker = stage / MANIFEST
            with marker.open("x", encoding="utf-8") as handle:
                json.dump(expected, handle, sort_keys=True, indent=2)
                handle.write("\n")
            read_publication(stage, job_id, request_key, settings)
            _sync_tree(stage)

            # Cooperative publishers are serialized; never replace an
            # existing destination observed within this ownership scope.
            if destination.exists() or destination.is_symlink():
                raise PublicationConflict("Destination appeared unexpectedly.")
            os.rename(stage, destination)
            _sync_directory(staging_root)
            _sync_directory(root)
            return destination
        finally:
            if stage.exists():
                shutil.rmtree(stage)
