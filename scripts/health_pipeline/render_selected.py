#!/usr/bin/env python3
"""Render one selected report from a versioned lineage artifact."""
import argparse
import json
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from analyse import analyse, load_config
from checks import validate
from common import write_json
from publish import render

HERE = Path(__file__).resolve().parent
PROFILE = HERE / "config/stakeholders/public_health_expert.json"
CLASSES = HERE / "config/pathogen_class.csv"
AUDIENCES = {
    "researcher": ("Technical disease-surveillance report", "Technical view of the selected disease-surveillance series."),
    "policy_maker": ("Disease-surveillance monitoring brief", "Monitoring summary of the selected disease notifications for decision support."),
    "general_public": ("Selected disease data: public summary", "Plain-language summary of the selected disease data. Notifications are not all infections."),
}

def results_root(path: Path) -> Path:
    matches = sorted(path.rglob("harmonised.parquet"), key=lambda p: len(p.parts))
    if not matches:
        raise FileNotFoundError("No harmonised.parquet in lineage artifact")
    root = matches[0].parent
    required = [root / "datasets.csv", root / "harmonised_snapshot.json", root / "reports/public_health_expert/data/series.csv"]
    if not all(p.is_file() for p in required):
        raise FileNotFoundError("Artifact is not a complete report lineage bundle")
    return root

def catalogue(root):
    bundle = root / "reports/public_health_expert/data"
    series = pd.read_csv(bundle / "series.csv").fillna("")
    selection = pd.read_csv(bundle / "selection.csv").fillna("")
    ok = selection[
        selection.status.astype(str).str.lower().eq("included")
        & selection.group_eligible.astype(str).str.lower().isin(["true", "1"])
    ]
    allowed = set(ok.dataset_id.astype(str))
    return series[
        series.dataset_id.astype(str).isin(allowed)
        & series.pathogen_class.isin(["viral", "bacterial"])
    ].drop_duplicates("dataset_id").sort_values(["pathogen_class", "label"])

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--lineage-root", required=True)
    p.add_argument("--audience", choices=AUDIENCES)
    p.add_argument("--selected-ids-json", required=True)
    p.add_argument("--source-run-id", required=True)
    p.add_argument("--request-id", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--quarto", default="quarto")
    args = p.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,40}", args.request_id):
        p.error("invalid request ID")
    selected_ids = json.loads(args.selected_ids_json)
    if not isinstance(selected_ids, list) or not selected_ids or len(selected_ids) != len(set(selected_ids)) or not all(isinstance(x, str) for x in selected_ids):
        p.error("selected IDs must be a non-empty JSON list of unique strings")

    root = results_root(Path(args.lineage_root))
    choices = catalogue(root)
    known = set(choices.dataset_id.astype(str))
    if unknown := set(selected_ids) - known:
        raise ValueError(f"Unusable selected datasets: {sorted(unknown)}")
    selected = choices[choices.dataset_id.astype(str).isin(selected_ids)]
    if selected.empty:
        raise ValueError("Select at least one eligible viral or bacterial dataset")
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=False)
    labels = dict(zip(selected.dataset_id.astype(str), selected.label.astype(str)))
    with tempfile.TemporaryDirectory(prefix="selected-report-") as tmp:
        work = Path(tmp)
        for name in ["datasets.csv", "harmonised_snapshot.json"]:
            shutil.copy2(root / name, work / name)
        data = pd.read_parquet(root / "harmonised.parquet")
        data[data.dataset_id.astype(str).isin(selected_ids)].to_parquet(work / "harmonised.parquet", index=False)
        validate(work)
        config = load_config(PROFILE)
        title, question = AUDIENCES[args.audience]
        config.update(id=args.audience, title=title, question=question)
        notes = dict(config.get("exclusion_notes", {}))
        notes["UI-selected datasets"] = ", ".join(f"{labels[x]} [{x}]" for x in selected_ids)
        notes["Lineage artifact run"] = str(args.source_run_id)
        config["exclusion_notes"] = notes
        config_path = work / "stakeholder.json"
        config_path.write_text(json.dumps(config, indent=2) + "\n")
        bundle = output / "data"
        analyse(work, config_path, CLASSES, bundle)

    provenance = {
        "schema_version": "1.0",
        "request_id": args.request_id,
        "audience": args.audience,
        "selected_dataset_ids": selected_ids,
        "selected_labels": [labels[x] for x in selected_ids],
        "lineage_artifact_run_id": str(args.source_run_id),
        "snapshot_id": json.loads((bundle / "bundle.json").read_text())["snapshot_id"],
        "rendered_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_json(output / "provenance.json", provenance)
    render(bundle, output / "report.html", "html", args.quarto)

if __name__ == "__main__":
    main()
