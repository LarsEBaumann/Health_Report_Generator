"""Portable, deterministic IO and integrity helpers shared by every stage."""
import hashlib
import json
from pathlib import Path

SCHEMA_VERSION = '2.0'

def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()

def object_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')
    tmp.replace(path)

def verify_gate(out):
    out = Path(out)
    gate = json.loads((out / 'validated.json').read_text())
    for name, expected in gate['files'].items():
        if digest(out / name) != expected:
            raise ValueError(f'Validation is stale: {name}; rerun checks')
    return gate
