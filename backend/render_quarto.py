#!/usr/bin/env python3
"""Render one Quarto report (reports/<report>.qmd) from the harmonised results.

The report code lives in reports/: the .qmd documents, shared/helpers.py,
shared/provenance.py and assets/swiss_cantons.geojson. Rendering happens in a temporary build directory, so a half-written
report is never published and two reports can render at the same time without racing over
Quarto's intermediate files. The cleaned table stays where it is; the build directory gets
only the report code, and HEALTH_RESULTS points it at the results directory.

Outputs, next to --output: <report>.html and provenance_<report>.json.

Usage:  python render_quarto.py --report researcher --results results \
            --output results/site/researcher.html --data-root data/reference
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
SOURCE = PROJECT / "reports"
# Copied flat into every build directory, because the .qmd documents import these by
# name and helpers.py reads the geojson from its own directory.
SHARED = [Path("shared/helpers.py"), Path("shared/provenance.py"),
          Path("assets/swiss_cantons.geojson")]
REQUIRED_INPUTS = ["harmonised.csv", "harmonised_snapshot.json", "datasets.csv", "checks.csv"]


def reports():
    return sorted(p.stem for p in SOURCE.glob("*.qmd"))


def render(report, results, output, quarto="quarto", data_root=None, topics=None):
    results = Path(results).resolve()
    output = Path(output).resolve()
    document = SOURCE / f"{report}.qmd"
    if not document.exists():
        raise SystemExit(f"no such report: {document} (available: {', '.join(reports())})")
    missing = [n for n in REQUIRED_INPUTS if not (results / n).exists()]
    if missing:
        raise SystemExit(f"missing pipeline outputs in {results}: {', '.join(missing)}")

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"quarto-{report}-") as tmp:
        build = Path(tmp)
        for name in SHARED + [Path(document.name)]:
            shutil.copyfile(SOURCE / name, build / name.name)
        env = os.environ.copy()
        env["HEALTH_RESULTS"] = str(results)
        env["HEALTH_REPORT_PROJECT"] = str(PROJECT)
        # Render with the interpreter that runs the pipeline: it is the one holding the
        # locked pandas, plotly and Jupyter kernel. Left to itself Quarto picks the first
        # python on PATH, which is a different installation and fails to start a kernel.
        env["QUARTO_PYTHON"] = sys.executable
        # provenance.py reads the retrieval records of the raw exports from here.
        if data_root:
            env["HEALTH_DATA_ROOT"] = str(Path(data_root).resolve())
        # Restricts the report to the diseases a reader selected; see helpers.SELECTED.
        if topics:
            env["HEALTH_TOPICS"] = ",".join(topics)
        subprocess.run([quarto, "render", document.name, "--to", "html"],
                       cwd=build, check=True, env=env)
        # Publish only after a successful render.
        shutil.copyfile(build / f"{report}.html", output)
        # Named after the output, not the report: two renders of the same report with
        # different disease selections write to different files and must not collide.
        provenance = build / f"provenance_{report}.json"
        if provenance.exists():
            shutil.copyfile(provenance, output.parent / f"provenance_{output.stem}.json")
    print(f"rendered {output}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True, help=f"one of: {', '.join(reports())}")
    ap.add_argument("--results", default="results")
    ap.add_argument("--output", required=True)
    ap.add_argument("--quarto", default="quarto")
    ap.add_argument("--data-root", help="raw exports the pipeline ingested, for provenance")
    ap.add_argument("--topics", help="comma-separated diseases to limit the report to "
                                     "(default: every disease)")
    a = ap.parse_args()
    topics = [t.strip() for t in (a.topics or '').split(',') if t.strip()]
    render(a.report, a.results, a.output, a.quarto, a.data_root, topics)
