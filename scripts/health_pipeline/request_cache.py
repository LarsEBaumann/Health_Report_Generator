"""Content-addressed cache for custom stakeholder reports.

A cached report is reused only when the validated request, the data snapshot,
the report code and the toolchain are all identical.
"""
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import analyse
import inventory
from common import SCHEMA_VERSION, digest, object_hash, write_json

ROOT = Path(__file__).resolve().parents[2]
CACHE_VERSION = '1'
ENTRY = 'cache_entry.json'
TOOLCHAIN_FILES = [
    'workflow/toolchain.json',
    'workflow/config.schema.json',
    'workflow/r-packages.tsv',
    'scripts/health_pipeline/requirements.lock.txt',
    'scripts/health_pipeline/requirements.ui.lock.txt',
]
IGNORED_TOP = {'__pycache__', 'example_output', 'config'}


def hash_files(paths, base):
    base = Path(base)
    entries = [{'path': Path(p).relative_to(base).as_posix(), 'sha256': digest(p)} for p in paths]
    return object_hash(sorted(entries, key=lambda e: e['path']))


def code_files(root=ROOT):
    base = Path(root) / 'scripts/health_pipeline'
    found = []
    for p in base.rglob('*'):
        parts = p.relative_to(base).parts
        if not p.is_file() or parts[0] in IGNORED_TOP or '__pycache__' in parts:
            continue
        if parts[0] == 'templates' or p.suffix in {'.py', '.qmd'}:
            found.append(p)
    return found


def request_key(request_path, manifest_path, root=ROOT):
    request = analyse.load_config(request_path)
    _, manifest = inventory.verify(manifest_path)
    root = Path(root)
    parts = {
        'cache_version': CACHE_VERSION,
        'schema_version': SCHEMA_VERSION,
        'request': request,
        'snapshot_id': manifest['snapshot_id'],
        'code_hash': hash_files(code_files(root), root),
        'toolchain_hash': hash_files([root / f for f in TOOLCHAIN_FILES], root),
    }
    return object_hash(parts), parts


def lookup(cache_root, key):
    entry_dir = Path(cache_root) / key
    entry_file = entry_dir / ENTRY
    if not entry_file.is_file():
        return None
    try:
        entry = json.loads(entry_file.read_text())
        if entry.get('key') != key:
            return None
        for rel, sha in entry['files'].items():
            if not (entry_dir / rel).is_file() or digest(entry_dir / rel) != sha:
                return None
    except (ValueError, KeyError, OSError):
        return None
    return entry_dir


def store(cache_root, key, parts, source_dir):
    cache_root = Path(cache_root)
    cache_root.mkdir(parents=True, exist_ok=True)
    hit = lookup(cache_root, key)
    if hit:
        return hit
    tmp = Path(tempfile.mkdtemp(dir=cache_root, prefix='.tmp-'))
    try:
        shutil.copytree(source_dir, tmp, dirs_exist_ok=True)
        files = {p.relative_to(tmp).as_posix(): digest(p) for p in sorted(tmp.rglob('*')) if p.is_file()}
        write_json(tmp / ENTRY, {
            'key': key,
            'components': parts,
            'created_utc': datetime.now(timezone.utc).isoformat(),
            'files': files,
        })
        target = cache_root / key
        if target.exists():
            shutil.rmtree(target)
        tmp.rename(target)
        return target
    finally:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)
