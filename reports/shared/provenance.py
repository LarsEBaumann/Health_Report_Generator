"""Provenance for the Quarto reports: which data, code and tools produced a report.

Each render writes provenance_<report>.json next to the report and prints a short
Provenance section, so every figure can be traced back to an exact input file.
"""
import base64
import hashlib
import json
import os
import platform
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import plotly

HERE = Path(__file__).resolve().parent
# See helpers.RESULTS: the pipeline overrides both the results directory and the
# repository root, because a render runs in a temporary build directory.
RESULTS = Path(os.environ.get("HEALTH_RESULTS") or HERE.parents[2] / "results")
PROJECT = Path(os.environ.get("HEALTH_REPORT_PROJECT") or HERE.parents[2])
# The raw exports the pipeline ingested; the Snakefile passes the configured data_root
# (workflow/config.yaml) through render_quarto.py.
DATA_ROOT = Path(os.environ.get("HEALTH_DATA_ROOT") or PROJECT / "data" / "reference")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _run(args: list[str]) -> str:
    exe = shutil.which(args[0])
    if exe is None:
        return "unavailable"
    try:
        return subprocess.check_output([exe, *args[1:]], cwd=PROJECT, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def data_retrieved() -> dict:
    """When the raw exports were downloaded, from the retrieval record of each dataset.

    Every dataset under the data root carries a retrieval.json written by the sync step,
    holding the exact `retrieved_at_utc` of that download. These recorded times are used
    rather than file timestamps, which a copy or a checkout resets.
    """
    stamps = []
    for record in sorted(DATA_ROOT.rglob("retrieval.json")) if DATA_ROOT.is_dir() else []:
        try:
            stamp = json.loads(record.read_text(encoding="utf-8")).get("retrieved_at_utc")
        except (OSError, ValueError):
            continue
        if stamp:
            stamps.append(stamp)
    if not stamps:
        return {"earliest": "unknown", "latest": "unknown",
                "basis": f"no retrieval.json found under {DATA_ROOT.name}"}
    stamps.sort()
    first, last = (datetime.fromisoformat(t).astimezone().isoformat(timespec="minutes")
                   for t in (stamps[0], stamps[-1]))
    return {"earliest": first, "latest": last,
            "basis": f"retrieved_at_utc recorded in retrieval.json of {len(stamps)} datasets"}


def selected_topics() -> dict:
    """The diseases this render was restricted to, if any; see helpers.SELECTED."""
    topics = [t.strip() for t in os.environ.get("HEALTH_TOPICS", "").split(",") if t.strip()]
    if not topics:
        return {}
    return {"Diseases selected": f"{len(topics)}: " + ", ".join(sorted(topics))}


def git() -> dict:
    """Without git, or outside a checkout, the working tree is unknown rather than dirty."""
    status = _run(["git", "status", "--porcelain"])
    return {"commit": _run(["git", "rev-parse", "HEAD"]),
            "uncommitted_changes": None if status == "unavailable" else bool(status)}


def build(report_file: str, parameters: dict | None = None) -> dict:
    cleaned = RESULTS / "harmonised.csv"
    snapshot = json.loads((RESULTS / "harmonised_snapshot.json").read_text(encoding="utf-8"))
    registry = pd.read_csv(RESULTS / "datasets.csv")
    used = registry[registry.status == "ok"].sort_values(["topic", "source_system"])
    checks = pd.read_csv(RESULTS / "checks.csv")
    return {
        "report": report_file,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "Federal Office of Public Health (FOPH) surveillance exports: one data.csv and metadata.json per dataset",
        "data_retrieved": data_retrieved(),
        "report_parameters": {**(parameters or {}), **selected_topics()},
        "input": {
            "file": "results/harmonised.csv",
            "sha256": sha256(cleaned),
            "bytes": cleaned.stat().st_size,
            "modified": datetime.fromtimestamp(cleaned.stat().st_mtime, timezone.utc).isoformat(timespec="seconds"),
            "produced_by": "backend/harmonise.py",
        },
        "raw_snapshot": {"snapshot_id": snapshot["snapshot_id"], "raw_files": len(snapshot["files"])},
        "datasets": [
            {"topic": r.topic, "source_system": r.source_system, "publishing_date": r.publishing_date,
             "rows": int(r.rows), "source_file": r.source_file, "sha256": r.sha256}
            for r in used.itertuples()],
        "raw_files_skipped_as_duplicates": int((registry.status == "duplicate_skipped").sum()),
        "quality_checks": {k: int(v) for k, v in checks.status.value_counts().items()},
        "code": {name: sha256(HERE / name) for name in [report_file, "helpers.py", "provenance.py"]},
        "git": git(),
        "environment": {"python": platform.python_version(), "pandas": pd.__version__, "plotly": plotly.__version__,
                        "quarto": _run(["quarto", "--version"]), "platform": platform.platform()},
    }


def section(report_file: str, parameters: dict | None = None) -> str:
    """Write the provenance JSON for this report and return the Provenance section as Markdown.

    `parameters` are the filters the report applies (audience, age, sex, geography, period).
    """
    p = build(report_file, parameters)
    json_name = f"provenance_{Path(report_file).stem}.json"
    record = json.dumps(p, indent=2, ensure_ascii=False) + "\n"
    (HERE / json_name).write_text(record, encoding="utf-8")
    # The report is sent around as a single HTML file, so the record is also embedded in it:
    # readable in a collapsible block and downloadable, without needing the separate JSON file.
    download = "data:application/json;base64," + base64.b64encode(record.encode("utf-8")).decode("ascii")

    env, checks = p["environment"], p["quality_checks"]
    dates = sorted(d["publishing_date"] for d in p["datasets"])
    got = p["data_retrieved"]
    retrieved = got["earliest"] if got["earliest"] == got["latest"] else f"{got['earliest']} to {got['latest']}"
    facts = [
        ("Source", p["source"]),
        ("Source publication dates", f"{dates[0]} to {dates[-1]}"),
        ("Data retrieved", f"{retrieved} ({got['basis']})"),
        ("Datasets ingested", f"{len(p['datasets'])} ({p['raw_files_skipped_as_duplicates']} duplicate raw files skipped)"),
        ("Cleaned input", f"`{p['input']['file']}`, {p['input']['bytes']:,} bytes, produced by `{p['input']['produced_by']}`"),
        ("Input checksum (SHA-256)", f"`{p['input']['sha256']}`"),
        ("Raw data snapshot", f"`{p['raw_snapshot']['snapshot_id']}` ({p['raw_snapshot']['raw_files']} files)"),
        ("Quality checks", ", ".join(f"{n} {status}" for status, n in sorted(checks.items()))),
        ("Code version (git commit)", f"`{p['git']['commit']}`" + (" plus uncommitted changes" if p["git"]["uncommitted_changes"] else "")),
        ("Tools", f"Python {env['python']}, pandas {env['pandas']}, plotly {env['plotly']}, Quarto {env['quarto']}"),
        ("Report generated (UTC)", p["generated_at"]),
    ]
    if p["report_parameters"]:
        facts.insert(3, ("Report parameters", "<br>".join(f"{k}: {v}" for k, v in p["report_parameters"].items())))
    lines = ["| Item | Value |", "|---|---|"] + [f"| {k} | {v} |" for k, v in facts]
    datasets = ["| Topic | Source system | Published | Rows | Raw file |", "|---|---|---|---|---|"] + [
        f"| {d['topic'].replace('_', ' ')} | {d['source_system'].replace('_', ' ')} | {d['publishing_date']} | "
        f"{d['rows']:,} | `{d['source_file']}` |" for d in p["datasets"]]
    return ("\n".join(lines)
            + "\n\nThe full machine-readable record, including the checksum of every raw file and of the report code, "
              f'is included below and can be saved as a file: <a download="{json_name}" href="{download}">'
              f"download {json_name}</a>.\n\n"
            + "<details><summary>Datasets behind this report</summary>\n\n" + "\n".join(datasets) + "\n\n</details>\n\n"
            + "<details><summary>Full provenance record (JSON)</summary>\n\n```json\n" + record + "```\n\n</details>\n")
