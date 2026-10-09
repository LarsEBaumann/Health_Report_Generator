"""Configured forks must be used by artifact lookup and workflow dispatch."""
import ast
import importlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
FORK = "example-user/example-fork"


@pytest.fixture
def connector_modules(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "src"))
    monkeypatch.setenv("GITHUB_REPOSITORY", FORK)
    monkeypatch.setenv("GITHUB_TOKEN", "test-token-not-a-real-secret")
    monkeypatch.setenv("GITHUB_OWNER", "wrong-owner")
    monkeypatch.setenv("GITHUB_REPO", "wrong-repo")
    monkeypatch.setenv("GITHUB_APP_REF", "main")
    monkeypatch.setenv("GITHUB_WORKFLOW", "update-lyme-data.yml")
    monkeypatch.setenv("GITHUB_BRANCH", "main")

    config = importlib.import_module("github_config")
    downloader = importlib.import_module("artifact_download")
    return config, downloader


def test_artifact_lookup_targets_configured_fork(
    connector_modules, monkeypatch
):
    _, downloader = connector_modules
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"workflow_runs": []},
        )

    monkeypatch.setattr(downloader.requests, "get", fake_get)

    with pytest.raises(RuntimeError, match="No successful"):
        downloader.download_latest_report()

    assert len(calls) == 1
    assert calls[0][0] == (
        f"https://api.github.com/repos/{FORK}/actions/workflows/"
        "update-lyme-data.yml/runs"
    )
    assert calls[0][1]["params"]["branch"] == "main"


def test_ui_dispatch_targets_configured_fork(connector_modules):
    config, _ = connector_modules
    tree = ast.parse((ROOT / "src/ui.py").read_text())
    cells = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and "report_form" in {arg.arg for arg in node.args.args}
    ]
    assert len(cells) == 1

    cell = cells[0]
    cell.decorator_list = []
    module = ast.Module(body=[cell], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {}
    exec(compile(module, str(ROOT / "src/ui.py"), "exec"), namespace)

    calls = []
    messages = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return SimpleNamespace(status_code=204, text="")

    def fake_markdown(text):
        messages.append(text)
        return text

    import requests

    fake_requests = SimpleNamespace(
        post=fake_post,
        RequestException=requests.RequestException,
    )
    fake_mo = SimpleNamespace(
        md=fake_markdown,
        callout=lambda content, **kwargs: content,
    )
    form = SimpleNamespace(value={
        "audience": "public",
        "bacterial": ["example-bacterial-dataset"],
        "viral": [],
    })

    namespace[cell.name](
        json=json,
        mo=fake_mo,
        os=os,
        report_form=form,
        requests=fake_requests,
        resolve_repository=config.resolve_repository,
        source_run={"id": 123, "run_number": 7},
        uuid=SimpleNamespace(
            uuid4=lambda: SimpleNamespace(hex="testrequest123")
        ),
    )

    assert len(calls) == 1
    url, kwargs = calls[0]
    assert url == (
        f"https://api.github.com/repos/{FORK}/actions/workflows/"
        "render-selected-report.yml/dispatches"
    )
    assert kwargs["json"]["ref"] == "main"
    assert kwargs["json"]["inputs"]["audience"] == "public"
    assert kwargs["json"]["inputs"]["lineage_run_id"] == "123"
    assert json.loads(
        kwargs["json"]["inputs"]["dataset_ids_json"]
    ) == ["example-bacterial-dataset"]
    assert any(f"github.com/{FORK}/actions/" in text for text in messages)
