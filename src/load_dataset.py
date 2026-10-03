from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd
import yaml

DATASET_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
CONFIG_PATH = Path("configs/report.yml")


def load_dataset(dataset_id: str | None = None) -> pd.DataFrame:
    if dataset_id is None:
        config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
        dataset_id = config.get("dataset_id")
    if not isinstance(dataset_id, str) or not DATASET_ID_PATTERN.fullmatch(dataset_id):
        raise ValueError("Set a valid dataset_id in configs/report.yml or pass --dataset")

    path = Path("data/reference") / dataset_id / "data.csv"
    if not path.is_file():
        raise FileNotFoundError(f"No downloaded IDD export for {dataset_id}: {path}")
    return pd.read_csv(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Load and inspect a selected IDD dataset")
    parser.add_argument("--dataset", help="IDD export identifier, e.g. LYME_sentinella")
    args = parser.parse_args()
    data = load_dataset(args.dataset)
    selected_id = args.dataset or yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))["dataset_id"]
    print(f"Dataset: {selected_id}")
    print(f"Rows: {len(data)}; columns: {len(data.columns)}")
    print("Columns:", ", ".join(data.columns))


if __name__ == "__main__":
    main()
