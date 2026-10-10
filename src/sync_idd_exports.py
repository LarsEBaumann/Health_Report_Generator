from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import sys
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
    reader = csv.reader(io.StringIO(text), strict=True)
    columns = next(reader, None)
    if not columns or any(not name.strip() for name in columns):
        raise ValueError("CSV has a missing or invalid header")

    row_count = 0
    for row_number, row in enumerate(reader, start=2):
        if not row:
            continue
        if len(row) != len(columns):
            raise ValueError(
                f"CSV row {row_number} has {len(row)} fields; "
                f"expected {len(columns)}"
            )
        row_count += 1

    if row_count == 0:
        raise ValueError("CSV contains no data rows")
    return columns, row_count

    row_count = 0
    for row_number, row in enumerate(reader, start=2):
        if not row:
            continue
        if len(row) != len(columns):
            raise ValueError(
                f"CSV row {row_number} has {len(row)} fields; "
                f"expected {len(columns)}"
            )
        row_count += 1

    if row_count == 0:
        raise ValueError("CSV contains no data rows")
    return columns, row_count

def fetch_validated_csv(session, url, known_sha=None, attempts=3):
    """Return (content, columns, rows). The server streams chunked, without
    Content-Length, so truncation is detected by matching hashes of two
    downloads, or by a match with the committed copy."""
    previous = None
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            response = session.get(url, timeout=(30, 300))
            response.raise_for_status()
            content = response.content
            columns, rows = csv_info(content)
        except (requests.RequestException, ValueError, csv.Error) as exc:
            last_error, previous = exc, None
            print(f"  attempt {attempt}/{attempts} failed: {exc}", flush=True)
            continue
        digest = sha256_bytes(content)
        if digest == known_sha or digest == previous:
            return content, columns, rows
        previous = digest
        print(f"  attempt {attempt}/{attempts}: unconfirmed, downloading again", flush=True)
    raise RuntimeError(f"no confirmed download after {attempts} attempts: {last_error}")


def sync_dataset(session, dataset_id):
    encoded_id = quote(dataset_id, safe="")
    csv_url = f"{API_ROOT}/{encoded_id}/csv"
    metadata_url = f"{API_ROOT}/{encoded_id}/metadata"
    dataset_dir = DATA_ROOT / dataset_id
    data_file = dataset_dir / "data.csv"
    metadata_file = dataset_dir / "metadata.json"
    retrieval_file = dataset_dir / "retrieval.json"

    print(f"CHECKING {dataset_id}: {csv_url}", flush=True)
    known_sha = sha256_bytes(data_file.read_bytes()) if data_file.is_file() else None
    csv_content, columns, row_count = fetch_validated_csv(session, csv_url, known_sha)

    metadata_response = session.get(metadata_url, timeout=60)
    metadata_response.raise_for_status()
    metadata = metadata_response.json()
    if not isinstance(metadata, dict):
        raise ValueError(f"IDD metadata for {dataset_id} was not a JSON object")
    metadata_content = (json.dumps(metadata, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    csv_sha256 = sha256_bytes(csv_content)
    metadata_sha256 = sha256_bytes(metadata_content)
    if (
        known_sha == csv_sha256
        and metadata_file.is_file()
        and sha256_bytes(metadata_file.read_bytes()) == metadata_sha256
    ):
        print(f"UNCHANGED {dataset_id} sha256={csv_sha256}")
        return "unchanged"

    retrieval = {
        "dataset_id": dataset_id,
        "csv_source_url": csv_url,
        "metadata_source_url": metadata_url,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "csv_sha256": csv_sha256,
        "metadata_sha256": metadata_sha256,
        "row_count": row_count,
        "columns": columns,
    }
    atomic_write(data_file, csv_content)
    atomic_write(metadata_file, metadata_content)
    atomic_write(retrieval_file, (json.dumps(retrieval, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(f"UPDATED {dataset_id}: {row_count} rows sha256={csv_sha256}")
    return "changed"


def main() -> None:
    session = requests.Session()
    session.headers.update({"User-Agent": "Health-Report-Generator/1.0"})

    response = session.get(CATALOG_URL, timeout=60)
    response.raise_for_status()
    dataset_ids = response.json()
    if not isinstance(dataset_ids, list) or not dataset_ids:
        raise ValueError("IDD export catalogue was not a non-empty list")
    if any(not isinstance(i, str) or not DATASET_ID_PATTERN.fullmatch(i) for i in dataset_ids):
        raise ValueError("IDD catalogue contains an invalid dataset identifier")

    counts = {"changed": 0, "unchanged": 0}
    failed = {}
    for dataset_id in dataset_ids:
        try:
            counts[sync_dataset(session, dataset_id)] += 1
        except Exception as exc:
            failed[dataset_id] = str(exc)
            print(f"FAILED {dataset_id}: {exc}", flush=True)

    print(f"Finished {len(dataset_ids)} IDD exports: {counts['changed']} changed, "
          f"{counts['unchanged']} unchanged, {len(failed)} failed")
    if failed:
        print("Not refreshed (last committed copy kept): " + ", ".join(sorted(failed)), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
