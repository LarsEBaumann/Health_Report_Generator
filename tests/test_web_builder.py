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


def test_context_carries_the_home_page_filters(web):
    """The home page offers pathogen class and year before an audience is chosen, so the
    context has to supply them without loading an audience payload."""
    data = body_of(web.context(Request()))
    assert set(data["filters"]) == {"years", "classes"}


def test_home_page_offers_class_year_and_stakeholder_icons():
    page = (ROOT / "frontend" / "web" / "page.html").read_text(encoding="utf-8")
    for needed in ('id="h-cls"', 'id="h-year"', 'class="who-pick"', 'data-who='):
        assert needed in page, needed
    # The large audience cards were replaced by the icon row.
    assert 'class="who-grid"' not in page


EXPECTED_TABS = {
    "researcher": ["Disease Explorer", "Seasonality & Geography",
                   "Comparative Analysis", "Data & Methods"],
    "health_institution": ["Surveillance Summary", "Priority Changes",
                           "Regional Monitoring", "Data Reliability"],
    "public": ["What's Happening?", "Explore Diseases",
               "In My Region", "Understanding the Data"],
}


def test_each_audience_has_its_own_named_dashboards(web):
    """Every audience's tabs follow its own report's argument."""
    audiences = {a["id"]: a for a in body_of(web.context(Request()))["audiences"]}
    for audience, names in EXPECTED_TABS.items():
        assert [t["name"] for t in audiences[audience]["tabs"]] == names, audience


def test_every_tab_carries_panels_or_charts(web):
    """A tab with neither would render as an empty page."""
    from frontend.web import figures
    for audience in body_of(web.context(Request()))["audiences"]:
        placed = {figures.tab_of(audience["id"], kind)
                  for kind in ("map", "annual", "season", "ages", "watch", "mover")}
        for tab in audience["tabs"]:
            assert tab["panels"] or tab["id"] in placed, (audience["id"], tab["id"])


def test_a_tab_without_panels_is_kept_for_its_charts(web):
    """Seasonality & Geography carries the report's map and heatmaps, and no panels."""
    audiences = {a["id"]: a for a in body_of(web.context(Request()))["audiences"]}
    geography = [t for t in audiences["researcher"]["tabs"] if t["id"] == "geography"]
    assert geography and geography[0]["panels"] == []
    # The same holds for the other audiences' map-only tabs.
    for audience, tab_id in [("health_institution", "regional"), ("public", "region")]:
        found = [t for t in audiences[audience]["tabs"] if t["id"] == tab_id]
        assert found and found[0]["panels"] == [], audience


def test_charts_are_placed_on_the_tabs_that_exist(web):
    """A chart must never be routed to a tab the audience does not have."""
    from frontend.web import figures
    for audience in body_of(web.context(Request()))["audiences"]:
        tabs = {t["id"] for t in audience["tabs"]}
        for kind in ("map", "annual", "season", "ages", "watch", "mover"):
            assert figures.tab_of(audience["id"], kind) in tabs, (audience["id"], kind)


def test_report_sections_are_served_verbatim(web):
    """The dashboards must show the report's own tables and prose, not a rewrite."""
    from frontend.web import sections
    found = sections.sections("researcher", "researcher")
    if not found:
        pytest.skip("no rendered report; run `python run.py` first")
    titles = {s["title"] for s in found}
    assert {"Methods", "Limitations", "Quality checks", "Provenance"} <= titles, titles
    for section in found:
        # A section that draws a chart is rebuilt by figures.py instead, because its
        # inline script would not run when the markup is injected into the page.
        assert "<script" not in section["html"], section["id"]
        assert section["html"].strip()


def test_data_and_methods_tab_carries_the_reports_methods(web):
    """The tab is named after the report's own sections, so it must contain them."""
    from frontend.web import sections
    found = sections.sections("researcher", "researcher")
    if not found:
        pytest.skip("no rendered report")
    on_tab = {s["title"] for s in found if s["tab"] == "methods"}
    assert {"Data at a glance", "Data coverage", "Quality checks",
            "Methods", "Limitations", "Provenance"} == on_tab


def test_sections_do_not_duplicate_a_panel(web):
    """Where the report supplies a section, the panel covering the same ground is gone."""
    audiences = {a["id"]: a for a in body_of(web.context(Request()))["audiences"]}
    methods = [t for t in audiences["researcher"]["tabs"] if t["id"] == "methods"][0]
    assert "quality" not in methods["panels"] and "sources" not in methods["panels"]
    diseases = [t for t in audiences["researcher"]["tabs"] if t["id"] == "diseases"][0]
    assert "disease_table" not in diseases["panels"]
