import os
import shutil
import tempfile
import zipfile
from pathlib import Path

import requests

API = "https://api.github.com"


def download_latest_report():
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("Set GITHUB_TOKEN with Actions read and write access.")

    owner = os.getenv("GITHUB_OWNER", "LarsEBaumann")
    repo = os.getenv("GITHUB_REPO", "Health_Report_Generator")
    workflow = os.getenv("GITHUB_WORKFLOW", "update-lyme-data.yml")
    branch = os.getenv("GITHUB_BRANCH", "main")
    # `researcher` is the default lineage bundle since Phase 5; older artifacts
    # only contain `public_health_expert`. An explicit setting is never overridden.
    requested = os.getenv("REPORT_DATA_STAKEHOLDER")
    candidates = [requested] if requested else ["researcher", "public_health_expert"]
    cache = Path(os.getenv("ARTIFACT_CACHE", ".cache/github-artifact"))
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

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
    if not artifacts:
        raise RuntimeError(f"Artifact {artifact_name} is missing or expired.")
    artifact = artifacts[0]

    extracted = cache / f"run-{run_id}-artifact-{artifact['id']}"
    marker = extracted / ".download-complete"
    if not marker.is_file():
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
                        raise RuntimeError("Unsafe path in artifact archive.")
                zf.extractall(dest)
            if extracted.exists():
                shutil.rmtree(extracted)
            shutil.copytree(dest, extracted)
            marker.write_text("ok", encoding="utf-8")

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
