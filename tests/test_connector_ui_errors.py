"""Connector errors must be visible without exposing raw response details."""
import ast
import importlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def dispatch_cell(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "src"))
    monkeypatch.setenv("GITHUB_REPOSITORY", "example-user/example-fork")
    monkeypatch.setenv("GITHUB_TOKEN", "test-token-not-a-real-secret")
    monkeypatch.setenv("GITHUB_APP_REF", "main")

    resolver = importlib.import_module("github_config").resolve_repository
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

    def invoke(post):
        messages = []
        callouts = []

        def markdown(text):
            messages.append(text)
            return text

        def callout(content, **kwargs):
            callouts.append(kwargs.get("kind"))
            return content

        namespace[cell.name](
            json=json,
            mo=SimpleNamespace(md=markdown, callout=callout),
            os=os,
            report_form=SimpleNamespace(value={
                "audience": "public",
                "bacterial": ["example-dataset"],
                "viral": [],
            }),
            requests=SimpleNamespace(
                post=post,
                RequestException=requests.RequestException,
            ),
            resolve_repository=resolver,
            source_run={"id": 123, "run_number": 7},
            uuid=SimpleNamespace(
                uuid4=lambda: SimpleNamespace(hex="testrequest123")
            ),
        )
        return messages, callouts

    return invoke


def test_invalid_repository_is_visible_and_blocks_dispatch(
    dispatch_cell, monkeypatch
):
    monkeypatch.setenv("GITHUB_REPOSITORY", "invalid/repo/extra")

    def forbidden_post(*args, **kwargs):
        pytest.fail("Invalid repository must not trigger a request.")

    messages, callouts = dispatch_cell(forbidden_post)
    assert any("Repository configuration error" in text for text in messages)
    assert "danger" in callouts


def test_missing_token_blocks_dispatch(dispatch_cell, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    def forbidden_post(*args, **kwargs):
        pytest.fail("Missing token must not trigger a request.")

    messages, callouts = dispatch_cell(forbidden_post)
    assert any("Set GITHUB_TOKEN" in text for text in messages)
    assert "warn" in callouts


@pytest.mark.parametrize(
    "status,expected",
    [
        (401, "token is valid"),
        (403, "Actions write permission"),
        (404, "render-selected-report.yml"),
        (422, "workflow branch and input values"),
        (500, "GitHub Actions/API status"),
    ],
)
def test_http_errors_have_safe_actionable_messages(
    dispatch_cell, status, expected
):
    sentinel = "RAW-RESPONSE-MUST-NOT-APPEAR"

    def fake_post(*args, **kwargs):
        return SimpleNamespace(status_code=status, text=sentinel)

    messages, callouts = dispatch_cell(fake_post)
    assert any(expected in text for text in messages)
    assert not any(sentinel in text for text in messages)
    assert "danger" in callouts


def test_network_exception_details_are_not_displayed(dispatch_cell):
    sentinel = "PRIVATE-NETWORK-DETAIL-MUST-NOT-APPEAR"

    def failing_post(*args, **kwargs):
        raise requests.RequestException(sentinel)

    messages, callouts = dispatch_cell(failing_post)
    assert any("Could not contact GitHub" in text for text in messages)
    assert not any(sentinel in text for text in messages)
    assert "danger" in callouts
