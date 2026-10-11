"""Freeze a local raw-data release; never fetch live data during reproduction."""
import argparse
import json
import shutil
from pathlib import Path
from common import digest, object_hash, write_json, SCHEMA_VERSION


def build(root, out):
    root, out = Path(root).resolve(), Path(out).resolve()
    if root == out or root in out.parents:
        raise ValueError('Snapshot output must be outside the raw input tree')
    files = sorted({p for csv in root.rglob('data.csv') for p in [csv, *csv.parent.glob('*.json')]}, key=lambda p: p.as_posix())
    if not any(p.name == 'data.csv' for p in files):
        raise ValueError('No data.csv files found')
    entries = [{'path': p.relative_to(root).as_posix(), 'sha256': digest(p), 'bytes': p.stat().st_size} for p in files]
    sid = object_hash(entries)
    target = out / 'snapshots' / sid
    for p, rec in zip(files, entries):
        dst = target / rec['path']
        if dst.exists():
            if digest(dst) != rec['sha256']:
                raise ValueError(f'Archived snapshot was modified: {dst}')
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, dst)
        if digest(dst) != rec['sha256']:
            raise ValueError(f'Input changed during snapshot: {p}')
    manifest = {'schema_version': SCHEMA_VERSION, 'snapshot_id': sid,
                'snapshot_path': f'snapshots/{sid}', 'files': entries}
    write_json(target / 'manifest.json', manifest)
    write_json(out / 'snapshot.json', manifest)
    return manifest


def verify(manifest_path):
    p = Path(manifest_path)
    m = json.loads(p.read_text())
    root = p.parent / m['snapshot_path'] if p.name == 'snapshot.json' else p.parent
    if object_hash(m['files']) != m['snapshot_id']:
        raise ValueError('Invalid snapshot manifest identity')
    for f in m['files']:
        if digest(root / f['path']) != f['sha256']:
            raise ValueError(f"Snapshot checksum mismatch: {f['path']}")
    return root, m

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('root'); ap.add_argument('--out', required=True)
    a = ap.parse_args(); build(a.root, a.out)
