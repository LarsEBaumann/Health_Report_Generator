import os
import json
import shutil
import tempfile
import time
import zipfile
from pathlib import Path

import requests

from github_config import resolve_repository

API = "https://api.github.com"


def _headers(token):
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _extract_artifact(artifact, headers, cache):
    """Download one Actions artifact without allowing unsafe archive paths."""
    cache = Path(cache)
    extracted = cache / f"artifact-{artifact['id']}"
    marker = extracted / ".download-complete"
    if marker.is_file():
        return extracted
    cache.mkdir(parents=True, exist_ok=True)
    response = requests.get(artifact["archive_download_url"], headers=headers, timeout=120)
    response.raise_for_status()
    with tempfile.TemporaryDirectory(dir=cache) as temp:
        temp = Path(temp)
        archive = temp / "artifact.zip"
        archive.write_bytes(response.content)
        dest = temp / "extracted"
        dest.mkdir()
        with zipfile.ZipFile(archive) as zf:
            base = dest.resolve()
            for item in zf.infolist():
                if not (dest / item.filename).resolve().is_relative_to(base):
                    raise RuntimeError("Unsafe path in GitHub artifact archive.")
            zf.extractall(dest)
        if extracted.exists():
            shutil.rmtree(extracted)
        shutil.copytree(dest, extracted)
        marker.write_text("ok", encoding="utf-8")
    return extracted


def _requested_report_dir(extracted, request_id):
    """Locate the exact report bundle identified by the Marimo request ID."""
    matches = []
    for result in Path(extracted).rglob("result.json"):
        try:
            record = json.loads(result.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if record.get("request", {}).get("request_id") == request_id:
            matches.append(result.parent)
    if len(matches) != 1:
        raise RuntimeError(f"Expected one report bundle for request {request_id!r}; found {len(matches)}.")
    report = matches[0]
    if not (report / "report.html").is_file():
        raise RuntimeError("The completed report artifact does not contain report.html.")
    return report


def wait_for_requested_report(request_id, ref=None, workflow=None, timeout_seconds=None, poll_seconds=None):
    """Wait for a dispatched report workflow and return its downloaded report bundle.

    The workflow run name contains the request ID, so concurrent users cannot be
    confused with one another's artifacts.  All report files are retrieved from
    GitHub Actions only after the matching run succeeds.
    """
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("Set GITHUB_TOKEN with Actions read and write access.")
    owner, repo = resolve_repository()
    ref = ref or os.getenv("GITHUB_APP_REF", "main")
    workflow = workflow or os.getenv("GITHUB_REQUEST_WORKFLOW", "request-report.yml")
    timeout_seconds = int(timeout_seconds or os.getenv("REPORT_WAIT_SECONDS", "600"))
    poll_seconds = int(poll_seconds or os.getenv("REPORT_POLL_SECONDS", "10"))
    headers = _headers(token)
    deadline = time.monotonic() + timeout_seconds
    run = None
    while time.monotonic() < deadline:
        url = f"{API}/repos/{owner}/{repo}/actions/workflows/{workflow}/runs"
        response = requests.get(url, headers=headers, params={
            "branch": ref, "event": "workflow_dispatch", "per_page": 100,
        }, timeout=30)
        response.raise_for_status()
        runs = response.json().get("workflow_runs", [])
        title = f"Requested report: {request_id}"
        run = next((item for item in runs if item.get("display_title") == title), None)
        if run is None:
            time.sleep(poll_seconds)
            continue
        if run.get("status") != "completed":
            time.sleep(poll_seconds)
            continue
        if run.get("conclusion") != "success":
            raise RuntimeError(
                f"Report request {request_id} ended with {run.get('conclusion')}. "
                f"Open {run.get('html_url')} for the job log."
            )
        artifacts_url = f"{API}/repos/{owner}/{repo}/actions/runs/{run['id']}/artifacts"
        artifacts = requests.get(artifacts_url, headers=headers, params={"per_page": 100}, timeout=30)
        artifacts.raise_for_status()
        expected_name = f"requested-health-report-{run['id']}"
        artifact = next((item for item in artifacts.json().get("artifacts", [])
                         if item.get("name") == expected_name and not item.get("expired")), None)
        if artifact is None:
            time.sleep(poll_seconds)
            continue
        cache = Path(os.getenv("ARTIFACT_CACHE", ".cache/github-artifact")) / "requested-reports"
        extracted = _extract_artifact(artifact, headers, cache)
        return _requested_report_dir(extracted, request_id), run, artifact
    raise RuntimeError(
        f"Report request {request_id} did not complete within {timeout_seconds} seconds. "
        "The GitHub run may still be active; use the Actions link to check it."
    )


def download_latest_report():
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("Set GITHUB_TOKEN with Actions read and write access.")

    owner, repo = resolve_repository()
    workflow = os.getenv("GITHUB_WORKFLOW", "validate.yml")
    branch = os.getenv("GITHUB_BRANCH", "main")
    # `researcher` is the default lineage bundle since Phase 5; older artifacts
    # only contain `public_health_expert`. An explicit setting is never overridden.
    requested = os.getenv("REPORT_DATA_STAKEHOLDER")
    candidates = [requested] if requested else ["researcher", "public_health_expert"]
    cache = Path(os.getenv("ARTIFACT_CACHE", ".cache/github-artifact"))
    headers = _headers(token)

    url = f"{API}/repos/{owner}/{repo}/actions/workflows/{workflow}/runs"
    response = requests.get(
        url, headers=headers,
        params={"branch": branch, "status": "success", "per_page": 20},
        timeout=30,
    )
    response.raise_for_status()
    runs = response.json().get("workflow_runs", [])
    runs = [r for r in runs if r.get("conclusion") == "success"]
    if not runs:
        raise RuntimeError(f"No successful {workflow} runs found on {branch}.")
    run = max(runs, key=lambda r: r["run_number"])
    run_id = run["id"]

    url = f"{API}/repos/{owner}/{repo}/actions/runs/{run_id}/artifacts"
    response = requests.get(url, headers=headers, params={"per_page": 100}, timeout=30)
    response.raise_for_status()
    artifact_name = f"health-report-{run_id}"
    artifacts = [
        a for a in response.json().get("artifacts", [])
        if a.get("name") == artifact_name and not a.get("expired")
    ]
    # validate.yml names its complete release after the commit SHA rather than
    # the Actions run ID. Keep the older exact convention when available and
    # otherwise accept the one release artifact from this validated run.
    if not artifacts:
        artifacts = [
            a for a in response.json().get("artifacts", [])
            if str(a.get("name", "")).startswith("health-report-") and not a.get("expired")
        ]
    if not artifacts:
        raise RuntimeError(f"A health-report artifact is missing or expired for {workflow} run {run_id}.")
    artifact = artifacts[0]

    extracted = _extract_artifact(artifact, headers, cache / f"run-{run_id}")

    bundles = [
        p.parent
        for p in extracted.rglob("series.csv")
        if (p.parent / "selection.csv").is_file()
    ]
    for stakeholder in candidates:
        preferred = [
            p for p in bundles
            if stakeholder in p.parts and p.name == "data"
        ]
        if len(preferred) == 1:
            return preferred[0], run, artifact
        if len(preferred) > 1:
            break
    raise RuntimeError(
        f"Expected one data bundle for stakeholder(s) {candidates!r}; "
        f"found: {[str(p) for p in bundles]}"
    )
