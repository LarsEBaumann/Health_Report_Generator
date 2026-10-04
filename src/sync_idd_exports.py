from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests

API_ROOT = "https://api.idd.bag.admin.ch/api/v1/export/latest"
CATALOG_URL = f"{API_ROOT}/files"
DATA_ROOT = Path("data/reference")
DATASET_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as tmp:
        tmp.write(content)
        temp_path = Path(tmp.name)
    os.replace(temp_path, path)


def csv_info(content: bytes) -> tuple[list[str], int]:
    text = content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text))
    columns = next(reader, None)
    if not columns or any(not name.strip() for name in columns):
        raise ValueError("CSV has a missing or invalid header")
    return columns, sum(1 for _ in reader)


def main() -> None:
    session = requests.Session()
    session.headers.update({"User-Agent": "Health-Report-Generator/1.0"})

    response = session.get(CATALOG_URL, timeout=60)
    response.raise_for_status()
    dataset_ids = response.json()
    if not isinstance(dataset_ids, list) or not dataset_ids:
        raise ValueError("IDD export catalogue was not a non-empty list")
    if any(not isinstance(dataset_id, str) or not DATASET_ID_PATTERN.fullmatch(dataset_id) for dataset_id in dataset_ids):
        raise ValueError("IDD catalogue contains an invalid dataset identifier")

    changed = 0
    unchanged = 0
    for dataset_id in dataset_ids:
        encoded_id = quote(dataset_id, safe="")
        csv_url = f"{API_ROOT}/{encoded_id}/csv"
        metadata_url = f"{API_ROOT}/{encoded_id}/metadata"

        csv_response = session.get(csv_url, timeout=120)
        csv_response.raise_for_status()
        csv_content = csv_response.content
        columns, row_count = csv_info(csv_content)

        metadata_response = session.get(metadata_url, timeout=60)
        metadata_response.raise_for_status()
        metadata = metadata_response.json()
        if not isinstance(metadata, dict):
            raise ValueError(f"IDD metadata for {dataset_id} was not a JSON object")
        metadata_content = (json.dumps(metadata, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

        csv_sha256 = sha256_bytes(csv_content)
        metadata_sha256 = sha256_bytes(metadata_content)
        dataset_dir = DATA_ROOT / dataset_id
        data_file = dataset_dir / "data.csv"
        metadata_file = dataset_dir / "metadata.json"
        retrieval_file = dataset_dir / "retrieval.json"

        unchanged_pair = (
            data_file.is_file()
            and metadata_file.is_file()
            and sha256_bytes(data_file.read_bytes()) == csv_sha256
            and sha256_bytes(metadata_file.read_bytes()) == metadata_sha256
        )
        if unchanged_pair:
            unchanged += 1
            print(f"UNCHANGED {dataset_id} sha256={csv_sha256}")
            continue

        retrieved_at = datetime.now(timezone.utc).isoformat()
        retrieval = {
            "dataset_id": dataset_id,
            "csv_source_url": csv_url,
            "metadata_source_url": metadata_url,
            "retrieved_at_utc": retrieved_at,
            "csv_sha256": csv_sha256,
            "metadata_sha256": metadata_sha256,
            "row_count": row_count,
            "columns": columns,
        }

        atomic_write(data_file, csv_content)
        atomic_write(metadata_file, metadata_content)
        atomic_write(retrieval_file, (json.dumps(retrieval, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        changed += 1
        print(f"UPDATED {dataset_id}: {row_count} rows sha256={csv_sha256}")

    print(f"Finished {len(dataset_ids)} IDD exports: {changed} changed, {unchanged} unchanged")


if __name__ == "__main__":
    main()
