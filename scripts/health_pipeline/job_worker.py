"""Process at most one queued job using trusted internal configuration."""

import json
import math
import sys
from pathlib import Path

from process_supervisor import run_supervised
from report_bundle import BundleInvalid
from report_publication import PublicationConflict, publish_bundle
from worker_session import worker_session


def run_one(
    store,
    *,
    workspace_root,
    published_root,
    data_root,
    cache_root,
    cwd,
    timeout=300,
    grace=1,
    renderer=None,
):
    """Own recovery, claiming, rendering and publication for one operation."""
    for name, value in (("timeout", timeout), ("grace", grace)):
        if (
            type(value) not in (int, float)
            or not math.isfinite(value)
            or value <= 0
        ):
            raise ValueError(f"{name} must be positive and finite.")

    cwd = Path(cwd).resolve()
    workspace_root = Path(workspace_root)
    published_root = Path(published_root)
    if workspace_root.is_symlink() or published_root.is_symlink():
        raise ValueError("Worker roots cannot be symlinks.")

    workspace_root = workspace_root.resolve()
    published_root = published_root.resolve()
    data_root = Path(data_root).resolve()
    cache_root = Path(cache_root).resolve()
    renderer = (
        Path(renderer).resolve()
        if renderer is not None
        else Path(__file__).resolve().with_name("custom_report.py")
    )

    with worker_session(store, published_root) as session:
        job = store.claim_next()
        if job is None:
            return None

        # A fresh directory is required; never overwrite an old workspace.
        workspace_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        workspace = workspace_root / job["job_id"]
        workspace.mkdir(mode=0o700)
        request_path = workspace / "request.json"
        with request_path.open("x", encoding="utf-8") as handle:
            json.dump(job["request"], handle, sort_keys=True, allow_nan=False)
            handle.write("\n")

        output = workspace / "report"
        result = run_supervised(
            [
                sys.executable,
                str(renderer),
                str(request_path),
                "--out", str(output),
                "--data-root", str(data_root),
                "--cache", str(cache_root),
            ],
            cwd=str(cwd),
            log_path=workspace / "render.log",
            lock_fd=session["lock_fd"],
            timeout=timeout,
            grace=grace,
        )

        if result.timed_out:
            store.finish(job["job_id"], "failed", "RENDER_TIMEOUT")
        elif result.returncode != 0:
            store.finish(job["job_id"], "failed", "RENDER_FAILED")
        else:
            try:
                publish_bundle(
                    output,
                    published_root,
                    job["job_id"],
                    job["request_key"],
                    job["request"],
                )
            except BundleInvalid:
                store.finish(job["job_id"], "failed", "REPORT_INVALID")
            except PublicationConflict:
                store.finish(job["job_id"], "failed", "PUBLICATION_INVALID")
            else:
                # Keep this outside publication exception handling.
                # If persistence fails, recovery must verify the publication.
                store.finish(job["job_id"], "completed")

        return store.get(job["job_id"])
