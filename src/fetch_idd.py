import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

SOURCE_URL = "https://www.idd.bag.admin.ch/api/v1/export/latest/LYME_sentinella/csv"
RAW_DIR = Path("data/raw")
REQUIRED_COLUMNS = {
    "valueCategory",
    "temporal",
    "georegion",
    "value",
    "dataComplete",
}


def main() -> None:
    response = requests.get(SOURCE_URL, timeout=60)
    response.raise_for_status()
    content = response.content

    rows = list(csv.DictReader(content.decode("utf-8-sig").splitlines()))
    if not rows:
        raise ValueError("The IDD response contained no CSV data.")

    columns = set(rows[0])
    missing = REQUIRED_COLUMNS - columns
    if missing:
        raise ValueError(f"IDD CSV is missing expected columns: {sorted(missing)}")

    retrieved_at = datetime.now(timezone.utc)
    stamp = retrieved_at.strftime("%Y%m%dT%H%M%SZ")
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    csv_path = RAW_DIR / f"lyme_sentinella_{stamp}.csv"
    metadata_path = RAW_DIR / f"lyme_sentinella_{stamp}.json"
    csv_path.write_bytes(content)

    metadata = {
        "source_url": SOURCE_URL,
        "retrieved_at_utc": retrieved_at.isoformat(),
        "sha256": hashlib.sha256(content).hexdigest(),
        "row_count": len(rows),
        "columns": list(rows[0]),
        "snapshot_file": csv_path.name,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")

    print(f"Saved {len(rows)} rows to {csv_path}")
    print(f"Provenance saved to {metadata_path}")
    print(f"SHA-256: {metadata['sha256']}")


if __name__ == "__main__":
    main()
