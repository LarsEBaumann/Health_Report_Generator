import os
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

import requests

API = "https://api.github.com"
TOKEN = os.environ["GITHUB_TOKEN"]
OWNER = os.environ["GITHUB_OWNER"]
REPO = os.environ["GITHUB_REPO"]
WORKFLOW = os.environ["GITHUB_WORKFLOW"]  # e.g. workflow.yml
BRANCH = os.getenv("GITHUB_BRANCH", "main")
ARTIFACT_NAME = os.getenv("GITHUB_ARTIFACT_NAME")  # optional filter
CACHE = Path(os.getenv("ARTIFACT_CACHE", ".cache/github-artifact"))


def headers():
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def get_json(url, **params):
    response = requests.get(
        url, headers=headers(), params=params, timeout=30
    )
    response.raise_for_status()
    return response.json()


def latest_run():
    url = f"{API}/repos/{OWNER}/{REPO}/actions/workflows/{WORKFLOW}/runs"
    data = get_json(
        url, branch=BRANCH, status="success", per_page=20
    )
    runs = [
        run for run in data["workflow_runs"]
        if run.get("conclusion") == "success"
    ]
    if not runs:
        raise RuntimeError(
            f"No successful runs found for {WORKFLOW} on {BRANCH}"
        )
    return max(runs, key=lambda run: run["run_number"])


def download_latest_report():
    run = latest_run()
    run_id = run["id"]

    artifacts_url = (
        f"{API}/repos/{OWNER}/{REPO}/actions/runs/{run_id}/artifacts"
    )
    artifacts = get_json(artifacts_url, per_page=100)["artifacts"]
    candidates = [
        artifact for artifact in artifacts
        if not artifact.get("expired")
        and (
            ARTIFACT_NAME is None
            or artifact["name"] == ARTIFACT_NAME
        )
    ]
    if not candidates:
        raise RuntimeError(
            f"No non-expired artifact found for workflow run {run_id}. "
            "Set GITHUB_ARTIFACT_NAME if the run has multiple artifacts."
        )

    artifact = max(candidates, key=lambda item: item["created_at"])
    if artifact.get("workflow_run", {}).get("id") not in (None, run_id):
        raise RuntimeError("Selected artifact does not belong to the chosen run")

    marker = CACHE / f"run-{run_id}-{artifact['id']}.complete"
    if not marker.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        response = requests.get(
            artifact["archive_download_url"],
            headers=headers(),
            timeout=120,
        )
        response.raise_for_status()

        with tempfile.TemporaryDirectory(dir=CACHE) as temp_dir:
            temp_dir = Path(temp_dir)
            archive = temp_dir / "artifact.zip"
            archive.write_bytes(response.content)

            extract_dir = temp_dir / "extracted"
            extract_dir.mkdir()
            with zipfile.ZipFile(archive) as zf:
                for member in zf.infolist():
                    target = (extract_dir / member.filename).resolve()
                    if not target.is_relative_to(extract_dir.resolve()):
                        raise RuntimeError("Unsafe path in artifact archive")
                zf.extractall(extract_dir)

            final_dir = CACHE / f"run-{run_id}-{artifact['id']}"
            if final_dir.exists():
                shutil.rmtree(final_dir)
            shutil.copytree(extract_dir, final_dir)
            marker.write_text("complete")

    extracted = CACHE / f"run-{run_id}-{artifact['id']}"
    parquet_files = list(extracted.rglob("harmonised.parquet"))
    if not parquet_files:
        raise FileNotFoundError(
            f"harmonised.parquet not found in downloaded artifact: {extracted}"
        )

    parquet = parquet_files[0]
    reports_dir = parquet.parent
    if not (reports_dir / "report.html").exists():
        html_files = list(extracted.rglob("report.html"))
        if html_files:
            reports_dir = html_files[0].parent

    return reports_dir, run, artifact



