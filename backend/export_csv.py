#!/usr/bin/env python3
"""Write the harmonised table as CSV for the Quarto reports.

harmonise.py stores the cleaned table as Parquet. The Quarto reports read a CSV and
record its checksum in their Provenance section, so the pipeline derives the CSV from
the Parquet rather than letting each report re-read a different file.

Usage:  python export_csv.py --out results/
"""
import argparse
from pathlib import Path

import pandas as pd


def export(out):
    out = Path(out)
    frame = pd.read_parquet(out / "harmonised.parquet")
    target = out / "harmonised.csv"
    tmp = target.with_suffix(".csv.tmp")
    frame.to_csv(tmp, index=False)
    tmp.replace(target)
    print(f"wrote {target} ({target.stat().st_size:,} bytes, {len(frame):,} rows)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results")
    export(ap.parse_args().out)
