import json
import subprocess
import sys
from pathlib import Path

import inventory

ROOT = Path(__file__).resolve().parents[1]


def prepare(tmp_path):
    raw = tmp_path / "raw" / "X_oblig"
    raw.mkdir(parents=True)
    (raw / "data.csv").write_text("a,b\n1,2\n")
    inventory.build(tmp_path / "raw", tmp_path / "snapshot")
    return {
        "out": str(tmp_path / "results"),
        "snapshot_manifest": str(tmp_path / "snapshot/snapshot.json"),
    }


def dry_run(tmp_path, config):
    override = tmp_path / "override.json"
    override.write_text(json.dumps(config))
    return subprocess.run(
        [
            sys.executable, "-m", "snakemake",
            "--snakefile", str(ROOT / "Snakefile"),
            "html", "--dry-run", "--cores", "1",
            "--configfile", str(override),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )


def test_default_stakeholder_directory_still_loads(tmp_path):
    config = prepare(tmp_path)
    config["stakeholders"] = ["public"]
    result = dry_run(tmp_path, config)
    assert result.returncode == 0, result.stdout + result.stderr


def test_private_stakeholder_directory_loads_without_shared_file(tmp_path):
    config = prepare(tmp_path)
    private = tmp_path / "private-stakeholders"
    private.mkdir()
    rid = "custom_123456789abc"
    shared_file = (
        ROOT / "scripts/health_pipeline/config/stakeholders" / f"{rid}.json"
    )
    assert not shared_file.exists()
    settings = json.loads(
        (ROOT / "scripts/health_pipeline/config/stakeholders/public.json")
        .read_text()
    )
    (private / f"{rid}.json").write_text(
        json.dumps({**settings, "id": rid})
    )
    config.update({"stakeholders": [rid], "stakeholder_dir": str(private)})
    result = dry_run(tmp_path, config)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not shared_file.exists()


def test_private_stakeholder_id_mismatch_is_rejected(tmp_path):
    config = prepare(tmp_path)
    private = tmp_path / "private-stakeholders"
    private.mkdir()
    rid = "custom_123456789abc"
    (private / f"{rid}.json").write_text(json.dumps({"id": "different"}))
    config.update({"stakeholders": [rid], "stakeholder_dir": str(private)})
    result = dry_run(tmp_path, config)
    assert result.returncode != 0
    assert "Stakeholder filename and id must match" in (
        result.stdout + result.stderr
    )
