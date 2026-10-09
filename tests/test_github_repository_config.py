"""Repository configuration must not silently redirect fork users."""
import importlib

import pytest


@pytest.fixture
def resolver(monkeypatch):
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root / "src"))
    for name in ("GITHUB_REPOSITORY", "GITHUB_OWNER", "GITHUB_REPO"):
        monkeypatch.delenv(name, raising=False)

    return importlib.import_module("github_config").resolve_repository


def test_primary_repository_wins(resolver, monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "example-user/example-fork")
    monkeypatch.setenv("GITHUB_OWNER", "different-owner")
    monkeypatch.setenv("GITHUB_REPO", "different-repo")
    assert resolver() == ("example-user", "example-fork")


def test_legacy_settings_work(resolver, monkeypatch):
    monkeypatch.setenv("GITHUB_OWNER", "example-user")
    monkeypatch.setenv("GITHUB_REPO", "example-fork")
    assert resolver() == ("example-user", "example-fork")


def test_blank_primary_uses_legacy_settings(resolver, monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "  ")
    monkeypatch.setenv("GITHUB_OWNER", "example-user")
    monkeypatch.setenv("GITHUB_REPO", "example-fork")
    assert resolver() == ("example-user", "example-fork")


def test_legacy_defaults_are_preserved(resolver):
    assert resolver() == ("LarsEBaumann", "Health_Report_Generator")


@pytest.mark.parametrize(
    "value",
    [
        "example-user",
        "/example-fork",
        "example-user/",
        "example-user/repo/extra",
        "https://github.com/example-user/repo",
        "example user/repo",
        "example-user/..",
    ],
)
def test_invalid_primary_does_not_fall_back(resolver, monkeypatch, value):
    monkeypatch.setenv("GITHUB_REPOSITORY", value)
    monkeypatch.setenv("GITHUB_OWNER", "valid-owner")
    monkeypatch.setenv("GITHUB_REPO", "valid-repo")
    with pytest.raises(ValueError):
        resolver()
