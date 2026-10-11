"""A second identical request must reuse the first report; any change must not."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/health_pipeline"))

import custom_report as cr  # noqa: E402

PUBLIC = ROOT / "scripts/health_pipeline/config/stakeholders/public.json"


@pytest.fixture
def setup(tmp_path):
    raw = tmp_path / "raw" / "X_oblig"
    raw.mkdir(parents=True)
    (raw / "data.csv").write_text("a,b\n1,2\n")
    request = json.loads(PUBLIC.read_text())
    path = tmp_path / "req.json"
    path.write_text(json.dumps(request))
    calls = []

    def render(req, rid, manifest, work_out):
        calls.append(rid)
        d = Path(work_out) / "reports" / rid
        d.mkdir(parents=True)
        (d / "report.html").write_text("<html>report</html>")
        (d / "provenance.json").write_text('{"rendered": "now"}')
        return d

    return tmp_path, path, calls, render


def run(tmp_path, path, render, name="out"):
    return cr.build_custom(path, tmp_path / "raw", tmp_path / name, tmp_path / "cache", render)


def test_miss_then_hit_renders_once(setup):
    tmp_path, path, calls, render = setup
    status1, key1, out1 = run(tmp_path, path, render, "out1")
    status2, key2, out2 = run(tmp_path, path, render, "out2")
    assert (status1, status2) == ("miss", "hit")
    assert key1 == key2 and len(calls) == 1
    assert (out2 / "report.html").read_text() == "<html>report</html>"
    assert json.loads((out2 / "request_provenance.json").read_text())["cache_key"] == key1


def test_changed_request_renders_again(setup):
    tmp_path, path, calls, render = setup
    run(tmp_path, path, render, "out1")
    request = json.loads(path.read_text())
    request["years"] = [2022, 2025]
    path.write_text(json.dumps(request))
    status, _, _ = run(tmp_path, path, render, "out2")
    assert status == "miss" and len(calls) == 2


def test_invalid_request_renders_nothing(setup):
    tmp_path, path, calls, render = setup
    request = json.loads(path.read_text())
    request["geography"] = "ZH"
    path.write_text(json.dumps(request))
    with pytest.raises(ValueError):
        run(tmp_path, path, render)
    assert calls == []



@pytest.mark.parametrize("fail", [False, True])
def test_private_stakeholder_removed_after_render(tmp_path, monkeypatch, fail):
    seen = {}
    shared = ROOT / "scripts/health_pipeline/config/stakeholders"
    before = {p.name: p.read_bytes() for p in shared.glob("*.json")}

    def fake_run(cmd, **kwargs):
        cfg_path = Path(cmd[-1])
        config = json.loads(cfg_path.read_text())
        private = Path(config["stakeholder_dir"])
        seen["private"] = private
        seen["config"] = config
        assert private.parent == tmp_path
        assert private != shared
        assert cfg_path.parent == private
        assert json.loads((private / "custom_abc123.json").read_text()) == {
            "years": [2022, 2025], "id": "custom_abc123",
        }
        assert config["stakeholders"] == ["custom_abc123"]
        assert config["out"] == str(tmp_path / "results")
        assert config["snapshot_manifest"] == str(tmp_path / "m.json")
        assert cmd[:2] == ["snakemake", "html"]
        assert kwargs["env"]["HEALTH_REPORT_HTML_ONLY"] == "1"
        if fail:
            raise cr.subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(cr.subprocess, "run", fake_run)
    if fail:
        with pytest.raises(cr.subprocess.CalledProcessError):
            cr.snakemake_render(
                {"years": [2022, 2025]}, "custom_abc123",
                tmp_path / "m.json", tmp_path / "results",
            )
    else:
        result = cr.snakemake_render(
            {"years": [2022, 2025]}, "custom_abc123",
            tmp_path / "m.json", tmp_path / "results",
        )
        assert result == tmp_path / "results/reports/custom_abc123"

    assert not seen["private"].exists()
    assert {p.name: p.read_bytes() for p in shared.glob("*.json")} == before
