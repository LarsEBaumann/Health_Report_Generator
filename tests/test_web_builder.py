"""The report builder page must work from a local build and refuse unsafe or impossible asks.

The handlers are called directly rather than through starlette.testclient, which would pull
in an HTTP client this project does not otherwise need.
"""
import asyncio
import json
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]


class Request:
    """The parts of a Starlette request these handlers use."""

    def __init__(self, body=None, **path_params):
        self._body = body or {}
        self.path_params = path_params

    async def json(self):
        return self._body


def body_of(response):
    return json.loads(bytes(response.body).decode("utf-8"))


@pytest.fixture
def web(monkeypatch, tmp_path):
    pytest.importorskip("starlette")
    monkeypatch.syspath_prepend(str(ROOT / "frontend"))
    monkeypatch.syspath_prepend(str(ROOT))
    for name in ("local_build", "frontend.web.app"):
        sys.modules.pop(name, None)
    # A minimal bundle, so the test needs no pipeline run.
    bundle = tmp_path / "reports/researcher/data"
    bundle.mkdir(parents=True)
    rows = [
        {"dataset_id": "flu__x", "topic": "influenza", "label": "Influenza",
         "pathogen_class": "viral"},
        {"dataset_id": "ehec__x", "topic": "ehec", "label": "EHEC",
         "pathogen_class": "bacterial"},
    ]
    pd.DataFrame(rows).to_csv(bundle / "series.csv", index=False)
    pd.DataFrame([{"dataset_id": r["dataset_id"], "status": "included",
                   "group_eligible": "True"} for r in rows]).to_csv(
        bundle / "selection.csv", index=False)
    from frontend.web import app as module
    # Patched through the app's own reference: frontend/local_build.py can be imported
    # under two names, and only the object the app holds matters here.
    monkeypatch.setattr(module.local_build, "RESULTS", tmp_path)
    monkeypatch.setattr(module.local_build, "SELECTED_DIR", tmp_path / "site/selected")
    monkeypatch.setattr(module, "FULL_SITE", tmp_path / "site")
    return module


def test_page_is_served(web):
    response = web.page(Request())
    assert response.status_code == 200
    body = bytes(response.body).decode("utf-8")
    assert "Infection Data Explorer" in body
    # The page must not pull anything off the network: it has to work offline.
    # (The SVG xmlns is a namespace identifier, not a fetch, so it is not a hit here.)
    remote = re.findall(r"""(?:src|href)\s*=\s*["']((?:https?:)?//[^"']+)""", body)
    remote += re.findall(r"@import[^;]+//", body)
    assert not remote, remote


def test_context_marks_audiences_without_a_local_report(web):
    data = body_of(web.context(Request()))
    audiences = {a["id"]: a for a in data["audiences"]}
    # The general public has no local Quarto report; the page must say so rather than
    # quietly serving a different audience's report.
    assert audiences["public"]["report"] is None
    assert audiences["researcher"]["report"] == "researcher"
    assert audiences["health_institution"]["report"] == "public_health"


def test_missing_local_build_is_explained(web, tmp_path, monkeypatch):
    monkeypatch.setattr(web.data, "RESULTS", tmp_path / "nothing-here")
    response = web.overview(Request(audience="researcher"))
    assert response.status_code == 503
    assert "run.py" in body_of(response)["error"]


def test_unknown_audience_is_refused(web):
    assert web.overview(Request(audience="nope")).status_code == 404


@pytest.mark.parametrize("payload,expected", [
    ({"audience": "researcher", "datasets": []}, "at least one disease"),
    ({"audience": "public", "datasets": ["flu__x"]}, "run.py release"),
    ({"audience": "researcher", "datasets": ["nope__x"]}, "not in the local bundle"),
])
def test_impossible_requests_are_refused_before_rendering(web, payload, expected):
    response = asyncio.run(web.render(Request(payload)))
    assert response.status_code == 400
    assert expected in body_of(response)["error"]


@pytest.mark.parametrize("name", ["../harmonised.csv", "..%2fharmonised.csv", "nope.html"])
def test_only_generated_reports_can_be_fetched(web, name):
    assert web.one_report(Request(name=name)).status_code == 404
    assert web.full_report(Request(name=name)).status_code == 404


def test_full_report_list_follows_the_configured_reports(web, tmp_path):
    site = tmp_path / "site"
    site.mkdir(parents=True, exist_ok=True)
    # A stray file in the output directory must not be offered as a full report.
    (site / "handwritten.html").write_text("stray", encoding="utf-8")
    (site / "researcher.html").write_text("real", encoding="utf-8")

    offered = body_of(web.context(Request()))["full_reports"]
    assert "handwritten.html" not in offered
    assert "researcher.html" in offered


def test_generated_reports_are_listed_newest_first(web):
    import os
    selected = web.local_build.SELECTED_DIR
    selected.mkdir(parents=True, exist_ok=True)
    for name in ("older.html", "newer.html"):
        (selected / name).write_text("x", encoding="utf-8")
    os.utime(selected / "older.html", (1, 1))

    listed = [item["name"] for item in web.previous_reports()]
    assert listed[0] == "newer.html" and "older.html" in listed
