from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import requests

SOURCE_URL = "https://www.idd.bag.admin.ch/api/v1/export/latest/LYME_sentinella/csv"
DATA_FILE = Path("data/reference/LYME_sentinella/data.csv")
METADATA_FILE = Path("data/reference/LYME_sentinella/metadata.json")
REQUIRED_COLUMNS = {
    "valueCategory",
    "temporal",
    "georegion",
    "value",
    "dataComplete",
}


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as tmp:
        tmp.write(content)
        temp_path = Path(tmp.name)
    os.replace(temp_path, path)


def main() -> None:
    response = requests.get(
        SOURCE_URL,
        headers={"User-Agent": "Health-Report-Generator/1.0"},
        timeout=60,
    )
    response.raise_for_status()
    content = response.content
    if not content.strip():
        raise ValueError("IDD API returned an empty response")

    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    columns = reader.fieldnames or []
    missing = REQUIRED_COLUMNS - set(columns)
    if missing:
        raise ValueError(f"IDD CSV is missing required columns: {sorted(missing)}")
    rows = list(reader)
    if not rows:
        raise ValueError("IDD CSV contains no data rows")

    digest = hashlib.sha256(content).hexdigest()
    if DATA_FILE.exists():
        previous_digest = hashlib.sha256(DATA_FILE.read_bytes()).hexdigest()
        if digest == previous_digest:
            print(f"UNCHANGED: {DATA_FILE} (sha256={digest})")
            return

    retrieved_at = datetime.now(timezone.utc).isoformat()
    metadata = {
        "source_url": SOURCE_URL,
        "retrieved_at_utc": retrieved_at,
        "sha256": digest,
        "row_count": len(rows),
        "columns": columns,
        "snapshot_file": DATA_FILE.name,
    }
    atomic_write(DATA_FILE, content)
    atomic_write(
        METADATA_FILE,
        (json.dumps(metadata, indent=2) + "\n").encode("utf-8"),
    )
    print(f"UPDATED: {DATA_FILE} ({len(rows)} rows, sha256={digest})")


if __name__ == "__main__":
    main()
