#!/usr/bin/env python3
"""Render one selected report from a versioned lineage artifact."""
import argparse
import json
import re
import shutil
import tempfile
from pathlib import Path

import pandas as pd
from analyse import analyse, load_config
from checks import validate
from publish import build_provenance, render

HERE = Path(__file__).resolve().parent
PROFILE = HERE / "config/stakeholders/public_health_expert.json"
CLASSES = HERE / "config/pathogen_class.csv"
# Lineage bundles produced by the default build. `researcher` shares the analytic
# parameters of the historical `public_health_expert` profile; older artifacts
# still contain only `public_health_expert`.
LINEAGE_STAKEHOLDERS = ("researcher", "public_health_expert")
AUDIENCES = {
    "researcher": ("Technical disease-surveillance report", "Technical view of the selected disease-surveillance series."),
    "health_institution": ("Disease-surveillance monitoring brief", "Monitoring summary of the selected disease notifications for decision support."),
    "public": ("Selected disease data: public summary", "Plain-language summary of the selected disease data. Notifications are not all infections."),
}

def results_root(path: Path) -> Path:
    matches = sorted(path.rglob("harmonised.parquet"), key=lambda p: len(p.parts))
    if not matches:
        raise FileNotFoundError("No harmonised.parquet in lineage artifact")
    root = matches[0].parent
    required = [root / "datasets.csv", root / "harmonised_snapshot.json"]
    if not all(p.is_file() for p in required) or lineage_bundle(root) is None:
        raise FileNotFoundError("Artifact is not a complete report lineage bundle")
    return root

def lineage_bundle(root):
    for stakeholder in LINEAGE_STAKEHOLDERS:
        bundle = root / "reports" / stakeholder / "data"
        if (bundle / "series.csv").is_file() and (bundle / "selection.csv").is_file():
            return bundle
    return None

def catalogue(root):
    bundle = lineage_bundle(root)
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
    p.add_argument("--audience", choices=AUDIENCES, required=True)
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
        shutil.copytree(root / "snapshots", work / "snapshots")
        data = pd.read_parquet(root / "harmonised.parquet")
        data[data.dataset_id.astype(str).isin(selected_ids)].to_parquet(work / "harmonised.parquet", index=False)
        validate(work)
        config = load_config(PROFILE)
        title, question = AUDIENCES[args.audience]
        config.update(id=args.audience, title=title, question=question)
        presentations = json.loads(
            (HERE / "config/audience_presentations.json").read_text()
        )
        presentation = {
            **presentations["profiles"][args.audience],
            "version": presentations["schema_version"],
        }
        config["presentation"] = presentation
        selected_classes = set(selected.pathogen_class.astype(str))
        config["classes_in_main_comparison"] = [
            cls for cls in ("viral", "bacterial")
            if cls in selected_classes
        ]
        notes = dict(config.get("exclusion_notes", {}))
        notes["UI-selected datasets"] = ", ".join(f"{labels[x]} [{x}]" for x in selected_ids)
        notes["Lineage artifact run"] = str(args.source_run_id)
        config["exclusion_notes"] = notes
        config_path = work / "stakeholder.json"
        config_path.write_text(json.dumps(config, indent=2) + "\n")
        bundle = output / "data"
        analyse(work, config_path, CLASSES, bundle)

        request_provenance = {
            "request_id": args.request_id,
            "audience": args.audience,
            "presentation": presentation,
            "selected_pathogen_classes": config["classes_in_main_comparison"],
            "output_formats": ["html", "pdf"],
            "selected_dataset_ids": selected_ids,
            "selected_labels": [labels[x] for x in selected_ids],
            "lineage_artifact_run_id": str(args.source_run_id),
        }

        snapshot = json.loads((bundle / "snapshot.json").read_text())
        snapshot_path = snapshot.get("snapshot_path")
        snapshot_root = work / snapshot_path if snapshot_path else None

        data_root = (
            snapshot_root
            if snapshot_root is not None and snapshot_root.is_dir()
            else None
        )

        workflow_path = Path(
            ".github/workflows/render-selected-report.yml"
        )
        workflow_config = {
            "path": workflow_path.as_posix(),
            "sha256": __import__("hashlib").sha256(
                workflow_path.read_bytes()
            ).hexdigest(),
        }

        html_provenance = build_provenance(
            bundle,
            "html",
            args.quarto,
            data_root=data_root,
            workflow_config=workflow_config,
            extra=request_provenance,
        )
        pdf_provenance = build_provenance(
            bundle,
            "pdf",
            args.quarto,
            data_root=data_root,
            workflow_config=workflow_config,
            extra=request_provenance,
        )

        # Record the artifact-relative location, not the disposable temp path.
        for record in (html_provenance, pdf_provenance):
            record["data"]["canonical_root"] = None
            record["data"]["snapshot_manifest"] = (
                "data/snapshot.json"
            )
            record["data"]["lineage_artifact_snapshot_path"] = snapshot_path

    render(
        bundle,
        output / "report.html",
        "html",
        args.quarto,
        provenance=html_provenance,
        provenance_out=output / "provenance.json",
    )
    render(
        bundle,
        output / "report.pdf",
        "pdf",
        args.quarto,
        provenance=pdf_provenance,
        provenance_out=output / "provenance-pdf.json",
    )
if __name__ == "__main__":
    main()
