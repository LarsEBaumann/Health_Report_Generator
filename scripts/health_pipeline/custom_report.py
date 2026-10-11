#!/usr/bin/env python3
"""Build one custom stakeholder report, or reuse an identical earlier one."""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import analyse
import inventory
import request_cache as rc
from common import write_json

ROOT = rc.ROOT


def snakemake_render(request, rid, manifest_path, work_out):
    """Render with private audience settings, never shared generated config."""
    work_out = Path(work_out).resolve()
    manifest_path = Path(manifest_path).resolve()
    with tempfile.TemporaryDirectory(
        prefix="stakeholder-", dir=work_out.parent
    ) as temporary:
        stakeholder_dir = Path(temporary)
        stakeholder_file = stakeholder_dir / f"{rid}.json"
        cfg_file = stakeholder_dir / "workflow_override.yaml"
        write_json(stakeholder_file, {**request, "id": rid})
        cfg_file.write_text(
            json.dumps({
                "out": str(work_out),
                "stakeholders": [rid],
                "stakeholder_dir": str(stakeholder_dir),
                "snapshot_manifest": str(manifest_path),
            }, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        subprocess.run(
            ["snakemake", "html", "--cores", "2", "--configfile", str(cfg_file)],
            cwd=ROOT, check=True,
            env={**os.environ, "HEALTH_REPORT_HTML_ONLY": "1"},
        )
    return work_out / "reports" / rid


def build_custom(request_path, data_root, out, cache, render=snakemake_render):
    cache, out = Path(cache), Path(out)
    request = analyse.load_config(request_path)
    snap_dir = cache / 'snapshot'
    inventory.build(data_root, snap_dir)
    manifest_path = snap_dir / 'snapshot.json'
    key, parts = rc.request_key(request_path, manifest_path)

    entry = rc.lookup(cache / 'entries', key)
    status = 'hit' if entry else 'miss'
    if not entry:
        rid = f'custom_{key[:12]}'
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = render(request, rid, manifest_path, Path(tmp) / 'results')
            write_json(Path(report_dir) / 'request_provenance.json', {
                'cache_key': key, 'components': parts,
                'rendered_utc': datetime.now(timezone.utc).isoformat(),
            })
            entry = rc.store(cache / 'entries', key, parts, report_dir)

    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(entry, out, ignore=shutil.ignore_patterns(rc.ENTRY))
    return status, key, out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('request')
    ap.add_argument('--out', required=True)
    ap.add_argument('--data-root', default='data/reference')
    ap.add_argument('--cache', default='results/cache/custom_reports')
    a = ap.parse_args()
    status, key, out = build_custom(a.request, a.data_root, a.out, a.cache)
    print(f'cache {status}: key={key} -> {out}')


if __name__ == '__main__':
    try:
        main()
    except ValueError as exc:
        sys.exit(f'Invalid request: {exc}')
