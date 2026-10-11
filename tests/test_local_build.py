"""The web interface must work from a local build, with no GitHub token or Actions run."""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def local_build(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "frontend"))
    sys.modules.pop("local_build", None)
    import local_build as module
    return module


def write_bundle(directory, rows, selection=None):
    """A minimal analysis bundle: the two files the interface reads."""
    directory.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(directory / "series.csv", index=False)
    if selection is None:
        selection = [{"dataset_id": r["dataset_id"], "status": "included",
                      "group_eligible": "True"} for r in rows]
    pd.DataFrame(selection).to_csv(directory / "selection.csv", index=False)
    return directory


ROWS = [
    {"dataset_id": "flu__x", "topic": "influenza", "label": "Influenza", "pathogen_class": "viral"},
    {"dataset_id": "ehec__x", "topic": "ehec", "label": "EHEC", "pathogen_class": "bacterial"},
    {"dataset_id": "waste__x", "topic": "wastewater", "label": "Wastewater", "pathogen_class": "other"},
]


def test_no_bundle_is_reported_rather_than_guessed(local_build, tmp_path, monkeypatch):
    monkeypatch.setattr(local_build, "RESULTS", tmp_path)
    assert local_build.bundle() is None


def test_bundle_is_found_and_filtered_like_the_interface(local_build, tmp_path, monkeypatch):
    monkeypatch.setattr(local_build, "RESULTS", tmp_path)
    write_bundle(tmp_path / "reports/researcher/data", ROWS)

    found = local_build.bundle()
    assert found == tmp_path / "reports/researcher/data"

    offered = local_build.datasets(found)
    # Only viral and bacterial series are selectable; other classes are not diseases.
    assert sorted(offered["dataset_id"]) == ["ehec__x", "flu__x"]


def test_ineligible_datasets_are_not_offered(local_build, tmp_path, monkeypatch):
    monkeypatch.setattr(local_build, "RESULTS", tmp_path)
    selection = [
        {"dataset_id": "flu__x", "status": "included", "group_eligible": "True"},
        {"dataset_id": "ehec__x", "status": "excluded", "group_eligible": "True"},
        {"dataset_id": "waste__x", "status": "included", "group_eligible": "False"},
    ]
    bundle = write_bundle(tmp_path / "reports/public/data", ROWS, selection)
    assert sorted(local_build.datasets(bundle)["dataset_id"]) == ["flu__x"]


def test_selected_datasets_become_report_topics(local_build, tmp_path, monkeypatch):
    monkeypatch.setattr(local_build, "RESULTS", tmp_path)
    bundle = write_bundle(tmp_path / "reports/researcher/data", ROWS)

    assert local_build.topics_for(bundle, ["flu__x", "ehec__x"]) == ["ehec", "influenza"]
    with pytest.raises(ValueError, match="not in the local bundle"):
        local_build.topics_for(bundle, ["nope__x"])


def test_topics_match_the_report_helpers(local_build, tmp_path, monkeypatch):
    """A topic chosen here must be one the reports know, or the render would reject it."""
    monkeypatch.syspath_prepend(str(ROOT / "reports/shared"))
    sys.modules.pop("helpers", None)
    import helpers

    monkeypatch.setattr(local_build, "RESULTS", tmp_path)
    bundle = write_bundle(tmp_path / "reports/researcher/data", ROWS)
    for topic in local_build.topics_for(bundle, ["flu__x", "ehec__x"]):
        assert topic in helpers.ALL_DISEASES


def test_audiences_without_a_local_report_say_so(local_build):
    assert local_build.report_for("researcher") == "researcher"
    assert local_build.report_for("health_institution") == "public_health"
    # `public` keeps only the R-rendered template; substituting another audience's report
    # would be wrong, so it must fail with an explanation.
    with pytest.raises(ValueError, match="python run.py release"):
        local_build.report_for("public")


def test_empty_selection_is_refused_before_rendering(local_build):
    with pytest.raises(ValueError, match="at least one disease"):
        local_build.render("researcher", [], "req1")


def test_local_reports_exist_for_every_mapped_audience(local_build):
    """The mapping must not point at a .qmd that is not in the repository."""
    for report in local_build.LOCAL_REPORTS.values():
        assert (ROOT / "reports" / f"{report}.qmd").exists(), report


def test_identical_requests_reuse_the_rendered_file(local_build, tmp_path, monkeypatch):
    """The same diseases, snapshot and report code must not be rendered twice."""
    monkeypatch.setattr(local_build, "RESULTS", tmp_path)
    monkeypatch.setattr(local_build, "SELECTED_DIR", tmp_path / "site/selected")
    write_bundle(tmp_path / "reports/researcher/data", ROWS)

    key = local_build.fingerprint("researcher", "researcher", ["influenza"])
    assert key == local_build.fingerprint("researcher", "researcher", ["influenza"])
    # Order must not matter, but the set of diseases must.
    assert (local_build.fingerprint("researcher", "researcher", ["influenza", "ehec"])
            == local_build.fingerprint("researcher", "researcher", ["ehec", "influenza"]))
    assert key != local_build.fingerprint("researcher", "researcher", ["ehec"])
    assert key != local_build.fingerprint("health_institution", "public_health", ["influenza"])

    # A file already there is returned without starting a render.
    local_build.SELECTED_DIR.mkdir(parents=True, exist_ok=True)
    already = local_build.SELECTED_DIR / f"researcher-{key}.html"
    already.write_text("earlier render", encoding="utf-8")

    def fail(*args, **kwargs):
        raise AssertionError("an identical request must not render again")

    monkeypatch.setattr(local_build.subprocess, "run", fail)
    assert local_build.render("researcher", ["influenza"]) == already
    assert already.read_text(encoding="utf-8") == "earlier render"
