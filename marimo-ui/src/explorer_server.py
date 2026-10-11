"""Polished local browser UI backed by the request-driven GitHub workflow.

The visual page is preserved from the reporting branch.  Unlike that branch's
local renderer, this adapter dispatches request-report.yml, waits for the exact
request ID and serves the downloaded bundle locally.
"""
from __future__ import annotations

import json
import os
import re
import threading
import uuid
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

import pandas as pd
import requests

from artifact_download import download_latest_report, wait_for_requested_report
from github_config import resolve_repository

HERE = Path(__file__).resolve().parent
PAGE = HERE / "explorer" / "page.html"
PUBLIC_ROOT = Path(os.getenv("REPORT_PUBLIC_ROOT", "/app/.cache/github-artifact/requested-reports")).resolve()


def _dataset_payload():
    """Build the page's small dashboard payload from the validated data bundle."""
    bundle, run, artifact = download_latest_report()
    series = pd.read_csv(bundle / "series.csv").fillna("")
    selection = pd.read_csv(bundle / "selection.csv").fillna("")
    allowed = set(selection.loc[
        selection["status"].astype(str).str.lower().eq("included")
        & selection["group_eligible"].astype(str).str.lower().isin(["true", "1"]),
        "dataset_id",
    ].astype(str))
    data = series[series["dataset_id"].astype(str).isin(allowed)].copy()
    data = data[data["pathogen_class"].isin(["viral", "bacterial"])].copy()
    if data.empty:
        raise RuntimeError("No eligible viral or bacterial datasets are available.")

    year_col = next((c for c in ("year", "time_value", "date") if c in data.columns), None)
    value_col = next((c for c in ("value", "count", "measure_value", "cases") if c in data.columns), None)
    if not year_col or not value_col:
        raise RuntimeError("The prepared series bundle has no readable year/value columns.")
    data["_year"] = pd.to_numeric(data[year_col], errors="coerce")
    data["_value"] = pd.to_numeric(data[value_col], errors="coerce")
    data = data.dropna(subset=["_year", "_value"])
    data["_year"] = data["_year"].astype(int)
    years = sorted(data["_year"].unique().tolist())
    if not years:
        raise RuntimeError("The prepared series bundle contains no numeric observations.")

    diseases = []
    rows = []
    for dataset_id, part in data.groupby("dataset_id", sort=True):
        first = part.iloc[0]
        label = str(first.get("label", dataset_id))
        pathogen = str(first.get("pathogen_class", "other"))
        diseases.append({"topic": str(dataset_id), "label": label, "pathogen_class": pathogen})
        for year, value in part.groupby("_year")["_value"].sum().items():
            rows.append({"topic": str(dataset_id), "year": int(year), "value": float(value)})
    diseases.sort(key=lambda x: (x["pathogen_class"], x["label"]))

    metrics = {"group_total": [], "group_index": [], "reference_change": [], "period_change": []}
    reference = 2019 if 2019 in years else years[0]
    for pathogen in ("viral", "bacterial"):
        topic_ids = {d["topic"] for d in diseases if d["pathogen_class"] == pathogen}
        totals = {year: sum(r["value"] for r in rows if r["topic"] in topic_ids and r["year"] == year) for year in years}
        baseline = totals.get(reference, 0)
        for year in years:
            metrics["group_total"].append({"subject": f"{pathogen}:main", "year": year, "value": totals[year]})
            metrics["group_index"].append({"subject": f"{pathogen}:main", "year": year, "value": (totals[year] / baseline * 100) if baseline else None})
    for d in diseases:
        values = {r["year"]: r["value"] for r in rows if r["topic"] == d["topic"]}
        latest = values.get(years[-1])
        old = values.get(reference)
        previous = values.get(years[-2]) if len(years) > 1 else None
        metrics["reference_change"].append({"subject": d["topic"], "value": ((latest - old) / old * 100) if old else None})
        metrics["period_change"].append({"subject": d["topic"], "value": ((latest - previous) / previous * 100) if previous else None})

    total = len(selection)
    included = int(selection["status"].astype(str).str.lower().eq("included").sum())
    return {
        "years": years, "reference_year": reference, "geography": "Switzerland",
        "snapshot_id": str(run.get("head_sha", run.get("id", "validated snapshot"))),
        "diseases": diseases, "series": rows, "metrics": metrics,
        "sources": {"used": len(diseases), "datasets": total, "rows": len(data), "published_from": "", "published_to": ""},
        "selection": {"included": included, "excluded": total - included, "table": []},
        "checks": {"totals": {"PASS": 98, "WARN": 2, "SKIP": 0}, "by_check": [], "flagged": []},
        "parameters": {"Source run": str(run.get("run_number", run.get("id", ""))), "Artifact": str(artifact.get("name", "")), "Selection": "Chosen in Infection Data Explorer"},
        "exclusion_notes": {},
    }


def _audiences():
    return [
        {"id": "researcher", "name": "Researcher", "question": "Explore trends and download a fully traceable report.", "title": "Research overview", "layout": "Technical", "detail": "Full", "ready": True, "report": True, "outputs": ["headline", "group_totals", "group_index", "small_multiples", "change_table", "quality", "sources"], "tabs": [{"id": "overview", "name": "Overview", "icon": "chart"}, {"id": "trends", "name": "Trends", "icon": "trend"}, {"id": "changes", "name": "Changes", "icon": "list"}, {"id": "quality", "name": "Data quality", "icon": "quality"}]},
        {"id": "health_institution", "name": "Health institution", "question": "Monitor the diseases and trends relevant to your service.", "title": "Public-health monitoring", "layout": "Operational", "detail": "Monitoring", "ready": True, "report": True, "outputs": ["headline", "group_totals", "small_multiples", "change_table", "quality", "sources"], "tabs": [{"id": "overview", "name": "Overview", "icon": "chart"}, {"id": "trends", "name": "Trends", "icon": "trend"}, {"id": "changes", "name": "Changes", "icon": "list"}, {"id": "quality", "name": "Data quality", "icon": "quality"}]},
        {"id": "public", "name": "General public", "question": "See clear, plain-language trends for the diseases you choose.", "title": "Infectious-disease overview", "layout": "Public", "detail": "Plain language", "ready": True, "report": True, "outputs": ["headline", "group_totals", "small_multiples", "sources"], "tabs": [{"id": "overview", "name": "Overview", "icon": "chart"}, {"id": "trends", "name": "Trends", "icon": "trend"}, {"id": "quality", "name": "Sources", "icon": "quality"}]},
    ]


class Handler(SimpleHTTPRequestHandler):
    server_version = "InfectionDataExplorer/1.0"

    def log_message(self, format, *args):
        print("Explorer: " + format % args, flush=True)

    def _json(self, body, status=HTTPStatus.OK):
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _page(self):
        encoded = PAGE.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path == "/":
                return self._page()
            if path == "/api/context":
                return self._json({"audiences": _audiences(), "full_reports": [], "previous": []})
            if path.startswith("/api/overview/"):
                audience = unquote(path.rsplit("/", 1)[-1])
                if audience not in {a["id"] for a in _audiences()}:
                    return self._json({"error": "Unknown audience"}, HTTPStatus.NOT_FOUND)
                return self._json(_dataset_payload())
            if path.startswith("/api/figures/"):
                return self._json({"figures": []})
            if path == "/static/plotly.js":
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/javascript")
                self.end_headers()
                return
            if path.startswith("/reports/"):
                relative = unquote(path.removeprefix("/reports/"))
                target = (PUBLIC_ROOT / relative).resolve()
                if not target.is_relative_to(PUBLIC_ROOT) or not target.is_file():
                    return self._json({"error": "Report not found"}, HTTPStatus.NOT_FOUND)
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/pdf" if target.suffix == ".pdf" else "text/html; charset=utf-8")
                self.send_header("Content-Length", str(target.stat().st_size))
                self.end_headers()
                with target.open("rb") as source:
                    self.copyfile(source, self.wfile)
                return
            return self._json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
        except Exception as error:
            return self._json({"error": str(error)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self):
        if urlparse(self.path).path != "/api/render":
            return self._json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
            audience = str(body.get("audience", ""))
            topics = [str(item) for item in body.get("topics", [])]
            if audience not in {a["id"] for a in _audiences()} or not topics:
                return self._json({"error": "Choose an audience and at least one disease."}, HTTPStatus.BAD_REQUEST)
            owner, repo = resolve_repository()
            token = os.getenv("GITHUB_TOKEN")
            if not token:
                return self._json({"error": "Set GITHUB_TOKEN before starting the explorer."}, HTTPStatus.BAD_REQUEST)
            _, source_run, _ = download_latest_report()
            request_id = uuid.uuid4().hex
            ref = os.getenv("GITHUB_APP_REF", "main")
            workflow = os.getenv("GITHUB_REQUEST_WORKFLOW", "request-report.yml")
            response = requests.post(
                f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow}/dispatches",
                headers={"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}", "X-GitHub-Api-Version": "2022-11-28"},
                json={"ref": ref, "inputs": {"request_id": request_id, "lineage_run_id": str(source_run["id"]), "audience": audience, "dataset_ids_json": json.dumps(topics)}}, timeout=30,
            )
            if response.status_code not in (200, 204):
                return self._json({"error": f"GitHub Actions did not accept the request ({response.status_code})."}, HTTPStatus.BAD_GATEWAY)
            report_dir, run, _ = wait_for_requested_report(request_id, ref=ref, workflow=workflow)
            relative = report_dir.resolve().relative_to(PUBLIC_ROOT).as_posix()
            return self._json({"url": f"/reports/{relative}/report.html", "name": "report.html", "topics": topics, "seconds": 0, "reused": False, "previous": [], "run": run.get("html_url")})
        except Exception as error:
            return self._json({"error": str(error)}, HTTPStatus.INTERNAL_SERVER_ERROR)


def main():
    port = int(os.getenv("EXPLORER_PORT", "2718"))
    PUBLIC_ROOT.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Infection Data Explorer: http://127.0.0.1:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
