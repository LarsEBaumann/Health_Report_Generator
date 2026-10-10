"""Cache keys must change with any input that changes the report, and only then."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/health_pipeline"))

import inventory  # noqa: E402
import request_cache as rc  # noqa: E402

PUBLIC = ROOT / "scripts/health_pipeline/config/stakeholders/public.json"


def write_request(tmp_path, name="req.json", **changes):
    request = json.loads(PUBLIC.read_text())
    request.update(changes)
    path = tmp_path / name
    path.write_text(json.dumps(request))
    return path


def make_snapshot(tmp_path, name, text="a,b\n1,2\n"):
    raw = tmp_path / f"raw_{name}" / "X_oblig"
    raw.mkdir(parents=True)
    (raw / "data.csv").write_text(text)
    inventory.build(raw.parent, tmp_path / f"out_{name}")
    return tmp_path / f"out_{name}" / "snapshot.json"


def test_key_is_stable_and_ignores_file_formatting(tmp_path):
    snap = make_snapshot(tmp_path, "one")
    first, _ = rc.request_key(write_request(tmp_path, "a.json"), snap)
    reordered = json.loads(PUBLIC.read_text())
    (tmp_path / "b.json").write_text(json.dumps(dict(reversed(list(reordered.items()))), indent=4))
    second, _ = rc.request_key(tmp_path / "b.json", snap)
    assert first == second


def test_key_changes_with_request(tmp_path):
    snap = make_snapshot(tmp_path, "one")
    base, _ = rc.request_key(write_request(tmp_path, "a.json"), snap)
    other, _ = rc.request_key(write_request(tmp_path, "b.json", years=[2022, 2025]), snap)
    assert base != other


def test_key_changes_with_snapshot(tmp_path):
    request = write_request(tmp_path)
    a, _ = rc.request_key(request, make_snapshot(tmp_path, "one"))
    b, _ = rc.request_key(request, make_snapshot(tmp_path, "two", text="a,b\n1,3\n"))
    assert a != b


def test_invalid_request_is_rejected(tmp_path):
    snap = make_snapshot(tmp_path, "one")
    with pytest.raises(ValueError):
        rc.request_key(write_request(tmp_path, bogus=1), snap)
    with pytest.raises(ValueError):
        rc.request_key(write_request(tmp_path, "g.json", geography="ZH"), snap)


def test_file_set_hash_changes_with_content(tmp_path):
    f = tmp_path / "code.py"
    f.write_text("x = 1\n")
    before = rc.hash_files([f], tmp_path)
    f.write_text("x = 2\n")
    assert rc.hash_files([f], tmp_path) != before


def test_store_lookup_and_corruption(tmp_path):
    src = tmp_path / "report"
    src.mkdir()
    (src / "index.html").write_text("<html>ok</html>")
    cache = tmp_path / "cache"
    assert rc.lookup(cache, "k1") is None
    stored = rc.store(cache, "k1", {"snapshot_id": "s"}, src)
    assert rc.lookup(cache, "k1") == stored
    assert rc.store(cache, "k1", {}, src) == stored
    (stored / "index.html").write_text("tampered")
    assert rc.lookup(cache, "k1") is None


def test_incomplete_entry_is_a_miss(tmp_path):
    (tmp_path / "cache" / "k2").mkdir(parents=True)
    assert rc.lookup(tmp_path / "cache", "k2") is None
