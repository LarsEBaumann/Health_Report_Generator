"""Render Isha's preserved Quarto templates from a validated report request.

The source templates in reporting/isha/source are never changed.  This adapter makes
an isolated build directory, stages the selected cached harmonised data in the
layout those templates expect, and renders a copy there.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SOURCE = REPO / "reporting" / "isha" / "source" / "reports"
TEMPLATES = {
    "researcher": "researcher.qmd",
    "health_institution": "public_health.qmd",
}
EXPECTED_COLUMNS = [
    "topic", "source_system", "measure", "period", "period_type", "place", "place_type",
    "age_group", "sex", "breakdown", "value", "pop", "incValue", "is_stat_row", "year",
]


def _request(bundle: Path) -> dict:
    return json.loads((bundle / "request.json").read_text(encoding="utf-8"))


def _selected_ids(bundle: Path) -> list[str]:
    selected = pd.read_csv(bundle / "selection.csv")
    if selected.empty or "dataset_id" not in selected:
        raise ValueError("Request selection has no resolved dataset IDs")
    return selected["dataset_id"].astype(str).tolist()


def _disease_mapping(bundle: Path, selected: pd.DataFrame) -> dict:
    """Give every requested topic a stable display label without editing template source."""
    sources = pd.read_csv(bundle / "sources.csv").fillna("")
    mapping = {}
    for row in sources.itertuples(index=False):
        topic = str(row.topic)
        label = topic.replace("_", " ").replace("-", " ").title()
        mapping[topic] = [label, "Selected surveillance data"]
    if not mapping:
        raise ValueError("Request source table is empty")
    return mapping


def _write_runtime_helpers(destination: Path, mapping: dict) -> None:
    """Copy a runtime helper with only its disease registry adapted to the request.

    The committed source helper remains byte-for-byte preserved.  The temporary copy
    accepts any validated topic selected through the request interface.
    """
    source = (SOURCE / "shared" / "helpers.py").read_text(encoding="utf-8")
    start = source.index("ALL_DISEASES = {")
    end = source.index("# A render can be restricted", start)
    registry = "ALL_DISEASES = " + json.dumps(mapping, indent=4, ensure_ascii=False) + "\n"
    (destination / "helpers.py").write_text(source[:start] + registry + source[end:], encoding="utf-8")
    shutil.copyfile(SOURCE / "shared" / "provenance.py", destination / "provenance.py")


def stage(bundle: Path, prepared: Path, build: Path) -> tuple[dict, str]:
    request = _request(bundle)
    if request["audience"] not in TEMPLATES:
        raise ValueError(f"Isha template is not configured for audience {request['audience']}")
    selected_ids = _selected_ids(bundle)
    data = pd.read_parquet(prepared / "harmonised.parquet")
    selected = data[data["dataset_id"].isin(selected_ids)].copy()
    if selected.empty:
        raise ValueError("The requested datasets produced no cached harmonised rows")
    missing = set(EXPECTED_COLUMNS) - set(selected.columns)
    if missing:
        raise ValueError("Prepared data is incompatible with Isha templates; missing " + ", ".join(sorted(missing)))

    results = build / "results"
    results.mkdir(parents=True)
    selected[EXPECTED_COLUMNS].to_csv(results / "harmonised.csv", index=False)

    registry = pd.read_csv(prepared / "datasets.csv")
    registry[registry["dataset_id"].isin(selected_ids)].to_csv(results / "datasets.csv", index=False)
    shutil.copyfile(prepared / "harmonised_snapshot.json", results / "harmonised_snapshot.json")
    shutil.copyfile(bundle / "checks.csv", results / "checks.csv")
    # Preserve the request contract beside the staged data for an audit trail.
    for name in ("request.json", "selection.csv", "sources.csv", "bundle.json"):
        shutil.copyfile(bundle / name, results / name)

    template = TEMPLATES[request["audience"]]
    shutil.copyfile(SOURCE / template, build / template)
    shutil.copytree(SOURCE / "assets", build / "assets")
    _write_runtime_helpers(build, _disease_mapping(bundle, selected))
    topics = ",".join(_disease_mapping(bundle, selected))
    return request, topics


def render(bundle, prepared, output, quarto="quarto"):
    bundle, prepared, output = Path(bundle), Path(prepared), Path(output)
    request = _request(bundle)
    if request["audience"] == "public":
        raise ValueError("Public reports use the existing request template; no Isha public template is configured")
    with tempfile.TemporaryDirectory(prefix="health-report-isha-") as directory:
        build = Path(directory)
        request, topics = stage(bundle, prepared, build)
        env = dict(os.environ)
        env.update({
            "HEALTH_RESULTS": str(build / "results"),
            "HEALTH_DATA_ROOT": str(build / "raw-not-included"),
            "HEALTH_REPORT_PROJECT": str(REPO),
            "HEALTH_TOPICS": topics,
        })
        template = TEMPLATES[request["audience"]]
        subprocess.run([quarto, "render", template, "--to", "html"], cwd=build, env=env, check=True)
        rendered = build / template.replace(".qmd", ".html")
        if not rendered.exists():
            raise RuntimeError("Quarto completed without producing the expected HTML report")
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(rendered, output)
        # QMD writes provenance beside helpers.py. Keep it next to the report when present.
        generated = build / f"provenance_{Path(template).stem}.json"
        if generated.exists():
            shutil.copyfile(generated, output.with_suffix(".template-provenance.json"))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--prepared", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--quarto", default="quarto")
    parser.add_argument("--stage-only", action="store_true")
    args = parser.parse_args(argv)
    if args.stage_only:
        target = Path(args.output)
        target.mkdir(parents=True, exist_ok=True)
        stage(Path(args.bundle), Path(args.prepared), target)
    else:
        render(args.bundle, args.prepared, args.output, args.quarto)


if __name__ == "__main__":
    main()
