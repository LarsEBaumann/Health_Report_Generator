"""Build a selected report on this machine, with no GitHub account, token or Actions run.

The web interface needs two things: a table of datasets a reader can choose from, and a way
to turn a choice into a report. Both already exist locally:

  * `snakemake tables` writes an analysis bundle per audience under
    results/reports/<audience>/data/, including the series.csv and selection.csv the
    interface reads. This needs no R.
  * backend/render_quarto.py renders reports/<name>.qmd, restricted to chosen diseases
    through --topics. These reports are Python (plotly + pandas), so they need Quarto but
    no R, TeX or Shiny.

The audiences that keep an R-rendered template (currently `public`) have no local Quarto
report, so this module reports them as unavailable rather than silently substituting a
different audience's report.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

PROJECT = Path(__file__).resolve().parents[1]
RESULTS = PROJECT / "results"
SELECTED_DIR = RESULTS / "site" / "selected"
BUNDLE_FILES = ("series.csv", "selection.csv")

# Audience id (workflow/config.yaml stakeholders) -> Quarto report in reports/.
# An audience absent here has no Python report and can only be built through the R path.
LOCAL_REPORTS = {
    "researcher": "researcher",
    "health_institution": "public_health",
}


def bundle() -> Path | None:
    """The newest local analysis bundle, or None if the pipeline has not produced one."""
    candidates = [
        directory for directory in sorted((RESULTS / "reports").glob("*/data"))
        if all((directory / name).exists() for name in BUNDLE_FILES)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda d: (d / "series.csv").stat().st_mtime)


def datasets(bundle_dir: Path) -> pd.DataFrame:
    """The eligible viral and bacterial datasets, one row each.

    Mirrors the filter the interface applies to a downloaded bundle, and additionally keeps
    `topic`, which is what a report is restricted by.
    """
    series = pd.read_csv(bundle_dir / "series.csv").fillna("")
    selection = pd.read_csv(bundle_dir / "selection.csv").fillna("")
    eligible = selection[
        selection["status"].astype(str).str.lower().eq("included")
        & selection["group_eligible"].astype(str).str.lower().isin(["true", "1"])
    ]
    allowed = set(eligible["dataset_id"].astype(str))
    chosen = series[
        series["dataset_id"].astype(str).isin(allowed)
        & series["pathogen_class"].isin(["viral", "bacterial"])
    ]
    return chosen.drop_duplicates("dataset_id").sort_values(["pathogen_class", "label"])


def topics_for(bundle_dir: Path, dataset_ids) -> list[str]:
    """The diseases behind the selected datasets, as topic ids a report understands."""
    wanted = {str(d) for d in dataset_ids}
    rows = datasets(bundle_dir)
    found = rows[rows["dataset_id"].astype(str).isin(wanted)]
    missing = wanted - set(found["dataset_id"].astype(str))
    if missing:
        raise ValueError(f"not in the local bundle: {', '.join(sorted(missing))}")
    return sorted({str(topic) for topic in found["topic"]})


def report_for(audience: str) -> str:
    """The Quarto report that serves this audience, or ValueError if none does."""
    try:
        return LOCAL_REPORTS[audience]
    except KeyError:
        raise ValueError(
            f"'{audience}' has no local Quarto report. Audiences available locally: "
            f"{', '.join(sorted(LOCAL_REPORTS))}. Build '{audience}' with "
            "`python run.py release`, which uses the R template."
        ) from None


def fingerprint(audience: str, report: str, topics) -> str:
    """Identifies a report by everything that can change it: the data snapshot, the report
    code, and the diseases chosen. The same request twice gives the same name."""
    parts = [audience, report, ",".join(sorted(topics))]
    snapshot = RESULTS / "harmonised_snapshot.json"
    if snapshot.exists():
        parts.append(json.loads(snapshot.read_text(encoding="utf-8")).get("snapshot_id", ""))
    for source in [PROJECT / "reports" / f"{report}.qmd",
                   PROJECT / "reports" / "shared" / "helpers.py",
                   PROJECT / "reports" / "shared" / "provenance.py"]:
        if source.exists():
            parts.append(hashlib.sha256(source.read_bytes()).hexdigest())
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:12]


def render(audience: str, topics, request_id: str = "", data_root="data/reference",
           reuse: bool = True) -> Path:
    """Render one selected report locally and return the file it wrote.

    An identical request -- same diseases, same data snapshot, same report code -- returns
    the file already on disk instead of spending another render on it. Pass reuse=False to
    force a rebuild.
    """
    topics = [str(t) for t in topics]
    if not topics:
        raise ValueError("Select at least one disease.")
    report = report_for(audience)
    SELECTED_DIR.mkdir(parents=True, exist_ok=True)
    output = SELECTED_DIR / f"{audience}-{fingerprint(audience, report, topics)}.html"
    if reuse and output.exists():
        return output
    command = [
        sys.executable, str(PROJECT / "backend/render_quarto.py"),
        "--report", report,
        "--results", str(RESULTS),
        "--output", str(output),
        "--data-root", data_root,
        "--topics", ",".join(topics),
    ]
    completed = subprocess.run(command, cwd=PROJECT, capture_output=True, text=True)
    if completed.returncode != 0:
        # The renderer's own message is the useful part; Quarto writes it to stderr.
        detail = (completed.stderr or completed.stdout or "").strip().splitlines()
        raise RuntimeError(detail[-1] if detail else "the renderer failed with no output")
    return output
