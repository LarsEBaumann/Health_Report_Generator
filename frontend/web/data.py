"""Turn the pipeline's analysis bundles into the figures the interface shows.

Everything here is read from results/reports/<audience>/data, which `snakemake tables`
writes: nothing is generated, estimated or filled in. Aggregation happens in pandas rather
than in the browser, so the page receives a few kilobytes of JSON instead of the tables.

Which panels an audience gets is not a decision made here either: it is the `outputs` list
in backend/config/stakeholders/<id>.json.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

PROJECT = Path(__file__).resolve().parents[2]
RESULTS = PROJECT / "results"
STAKEHOLDERS = PROJECT / "backend" / "config" / "stakeholders"
CONFIG = PROJECT / "workflow" / "config.yaml"

# Panel ids come from each audience's `outputs`; these group them into tabs, in order.
TABS = [
    {"id": "overview", "name": "Overview", "icon": "chart", "panels": ["headline", "group_totals"]},
    {"id": "trends", "name": "Trends", "icon": "trend", "panels": ["group_index", "small_multiples"]},
    {"id": "changes", "name": "Changes", "icon": "list", "panels": ["change_table", "excluded"]},
    {"id": "quality", "name": "Quality & sources", "icon": "quality", "panels": ["quality", "sources"]},
]


def _rows(frame: pd.DataFrame) -> list[dict]:
    """Records with NaN turned into null, which json.dumps cannot emit otherwise."""
    return frame.astype(object).where(pd.notna(frame), None).to_dict("records")


def stakeholder_ids() -> list[str]:
    """The audiences the workflow builds, in the order workflow/config.yaml lists them."""
    ids, inside = [], False
    for line in CONFIG.read_text(encoding="utf-8").splitlines():
        if line.startswith("stakeholders:"):
            inside = True
        elif inside and line.strip().startswith("- "):
            ids.append(line.strip()[2:].strip())
        elif inside and line and not line.startswith((" ", "-", "#")):
            break
    return ids


def bundle(audience: str) -> Path | None:
    directory = RESULTS / "reports" / audience / "data"
    return directory if (directory / "series.csv").exists() else None


def audiences(local_reports: dict) -> list[dict]:
    """Each audience with its own configured wording, parameters and panel list."""
    out = []
    for audience in stakeholder_ids():
        config = STAKEHOLDERS / f"{audience}.json"
        if not config.exists():
            continue
        spec = json.loads(config.read_text(encoding="utf-8"))
        presentation = spec.get("presentation") or {}
        out.append({
            "id": audience,
            "name": presentation.get("display_name", audience),
            "title": spec["title"],
            "question": spec["question"],
            "layout": presentation.get("layout", ""),
            "detail": presentation.get("detail_level", ""),
            "outputs": spec.get("outputs", []),
            "years": spec.get("years"),
            "reference_year": spec.get("reference_year"),
            "geography": spec.get("geography"),
            "report": local_reports.get(audience),
            "ready": bundle(audience) is not None,
            "tabs": [tab for tab in TABS
                     if any(panel in spec.get("outputs", []) for panel in tab["panels"])],
        })
    return out


def _checks(directory: Path) -> dict:
    checks = pd.read_csv(directory / "checks.csv")
    by_check = (checks.groupby(["check", "status"]).size().unstack(fill_value=0)
                .reindex(columns=["PASS", "WARN", "FAIL", "SKIP"], fill_value=0)
                .reset_index().sort_values("check"))
    flagged = checks[checks.status.isin(["WARN", "FAIL"])]
    return {
        "totals": checks.status.value_counts().to_dict(),
        "by_check": _rows(by_check),
        "flagged": _rows(flagged[["dataset_id", "check", "status", "detail"]]),
    }


def _sources(directory: Path) -> dict:
    sources = pd.read_csv(directory / "sources.csv")
    used = sources[sources.status == "ok"]
    publishing = sorted(d for d in used.publishing_date.dropna().astype(str))
    return {
        "datasets": int(len(sources)),
        "used": int(len(used)),
        "rows": int(used.rows.fillna(0).sum()),
        "published_from": publishing[0] if publishing else None,
        "published_to": publishing[-1] if publishing else None,
        "table": _rows(used[["topic", "source_system", "publishing_date", "rows", "sha256"]]
                       .sort_values(["topic", "source_system"])),
    }


def _selection(directory: Path) -> dict:
    selection = pd.read_csv(directory / "selection.csv")
    excluded = selection[selection.status.astype(str).str.lower() != "included"]
    return {
        "included": int((selection.status.astype(str).str.lower() == "included").sum()),
        "excluded": int(len(excluded)),
        "table": _rows(excluded[["topic", "source_system", "status", "reason"]]
                       .sort_values(["status", "topic"])),
    }


def payload(audience: str, local_reports: dict) -> dict | None:
    """Everything the dashboards for one audience need, in one response."""
    directory = bundle(audience)
    if directory is None:
        return None

    series = pd.read_csv(directory / "series.csv")
    metrics = pd.read_csv(directory / "metrics.csv")
    spec = json.loads((directory / "stakeholder.json").read_text(encoding="utf-8"))
    info = json.loads((directory / "bundle.json").read_text(encoding="utf-8"))

    kinds = {kind: _rows(metrics[metrics.metric_type == kind]
                         [["subject", "year", "unit", "value", "formula"]])
             for kind in ["group_index", "group_total", "reference_change", "period_change"]}

    diseases = (series[["topic", "label", "pathogen_class"]].drop_duplicates("topic")
                .sort_values(["pathogen_class", "label"]))
    return {
        "audience": audience,
        "snapshot_id": info.get("snapshot_id"),
        "years": sorted(int(y) for y in series.year.unique()),
        "reference_year": spec.get("reference_year"),
        "geography": spec.get("geography"),
        "diseases": _rows(diseases),
        "series": _rows(series[["topic", "label", "pathogen_class", "measure", "year",
                                "value", "incidence", "coverage"]]),
        "metrics": kinds,
        "checks": _checks(directory),
        "selection": _selection(directory),
        "sources": _sources(directory),
        "parameters": {
            "Years compared": f"{spec['years'][0]}–{spec['years'][1]}",
            "Reference year": spec.get("reference_year"),
            "Index base year": spec.get("index_base_year"),
            "Geography": spec.get("geography"),
            "Compared by": spec.get("compare_by"),
            "Classes compared": ", ".join(spec.get("classes_in_main_comparison", [])),
            "Measures preferred": ", ".join(spec.get("measures_preferred", [])),
            "Excluded from group totals": ", ".join(spec.get("exclude_from_group_totals", [])) or "none",
            "Sensitivity exclusion": ", ".join(spec.get("sensitivity_exclude", [])) or "none",
        },
        "exclusion_notes": spec.get("exclusion_notes", {}),
    }
