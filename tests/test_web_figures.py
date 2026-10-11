"""Dashboard charts must come from the reports' own plotting code, not a second copy of it."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "frontend" / "web" / "page.html"
needs_build = pytest.mark.skipif(
    not (ROOT / "results" / "harmonised.csv").exists(),
    reason="no local build; run `python run.py` first")


@pytest.fixture
def figures(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT))
    sys.modules.pop("frontend.web.figures", None)
    from frontend.web import figures as module
    module._cache.clear()
    return module


def test_the_helpers_behind_the_charts_are_the_reports_own(figures):
    """The module must import reports/shared/helpers.py, the file the .qmd documents use."""
    import helpers
    assert Path(helpers.__file__).resolve() == (ROOT / "reports" / "shared" / "helpers.py").resolve()


def test_report_assets_resolve_from_both_layouts():
    """A render flattens assets next to helpers.py; in the repository they sit in assets/."""
    sys.path.insert(0, str(ROOT / "reports" / "shared"))
    import helpers
    found = helpers.asset("swiss_cantons.geojson")
    assert found.exists()
    with pytest.raises(FileNotFoundError):
        helpers.asset("not-a-real-asset.geojson")


@needs_build
@pytest.mark.parametrize("detail,expect", [
    ("monitoring", "watch-"),       # what is above its usual level
    ("full", "season-"),            # the diagnostic detail
    ("plain_language", "mover-"),   # the few series that moved most
])
def test_each_audience_gets_the_charts_its_detail_level_calls_for(figures, detail, expect):
    built = figures.build("x", detail)
    ids = [f["id"] for f in built]
    assert any(i.startswith(expect) for i in ids), ids
    # The map and the long-term panel are common ground for every audience.
    assert "map" in ids and "annual" in ids


@needs_build
def test_every_figure_is_renderable_and_placed(figures):
    for figure in figures.build("x", "full"):
        assert figure["tab"] in {"overview", "trends"}, figure["id"]
        assert figure["title"] and figure["note"]
        assert figure["spec"].get("data"), figure["id"]
        # Must survive the trip through JSON: plotly leaves numpy types in its objects.
        import json
        json.dumps(figure["spec"])


@needs_build
def test_figures_are_cached_per_audience(figures, monkeypatch):
    figures.figures("researcher", "full")

    def fail(*args, **kwargs):
        raise AssertionError("a cached audience must not be rebuilt")

    monkeypatch.setattr(figures, "build", fail)
    assert figures.figures("researcher", "full")


def test_chart_library_is_served_locally(figures):
    """A CDN would break the page offline, so plotly comes from the installed package."""
    assert "Plotly" in figures.plotly_js()[:5000]
    body = PAGE.read_text(encoding="utf-8")
    assert "/static/plotly.js" in body
    assert "/api/figures/" in body
