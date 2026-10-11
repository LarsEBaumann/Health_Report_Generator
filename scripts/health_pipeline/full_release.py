#!/usr/bin/env python3
"""Create reproducible all-audience requests from the validated legacy selection."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

AUDIENCES = ("researcher", "health_institution", "public")


def true(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--formats", default="html,pdf")
    args = parser.parse_args()

    with args.selection.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    datasets = sorted({
        row["dataset_id"] for row in rows
        if row.get("status", "").strip().lower() == "included"
        and true(row.get("group_eligible", ""))
        and row.get("dataset_id")
    })
    if not datasets:
        raise SystemExit("The validated release contains no eligible datasets for the full audience reports.")

    formats = [item.strip() for item in args.formats.split(",") if item.strip()]
    if not formats or any(item not in {"html", "pdf"} for item in formats):
        raise SystemExit("--formats must be a comma-separated subset of html,pdf")
    args.out.mkdir(parents=True, exist_ok=True)
    for audience in AUDIENCES:
        request = {
            "schema_version": "1.0",
            "request_id": f"full-release-{audience}",
            "lineage_run_id": "full-release",
            "audience": audience,
            "datasets": datasets,
            "formats": formats,
        }
        (args.out / f"{audience}.json").write_text(json.dumps(request, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(AUDIENCES)} full-release requests for {len(datasets)} validated datasets.")


if __name__ == "__main__":
    main()
