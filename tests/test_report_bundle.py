import json

import pytest

from report_bundle import BundleInvalid, verify_bundle


@pytest.fixture
def bundle(tmp_path):
    root = tmp_path / "bundle"
    root.mkdir()
    settings = {"id": "public", "years": [2022, 2025], "geography": "CHFL"}
    effective = {**settings, "id": "custom_0123456789ab"}
    (root / "report.html").write_text(
        '<html><a href="methods.html">Methods</a></html>'
    )
    (root / "methods.html").write_text("<html>Methods</html>")
    (root / "provenance.json").write_text(
        json.dumps({"effective_parameters": effective})
    )
    (root / "request_provenance.json").write_text(
        json.dumps({"cache_key": "a" * 64})
    )
    return root, settings


def test_valid_bundle_has_hash_inventory(bundle):
    root, settings = bundle
    result = verify_bundle(root, settings)
    assert len(result["files"]) == 4
    assert result["cache_key"] == "a" * 64
    assert all(len(value) == 64 for value in result["files"].values())


def test_missing_core_artifact_is_rejected(bundle):
    root, settings = bundle
    (root / "methods.html").unlink()
    with pytest.raises(BundleInvalid):
        verify_bundle(root, settings)


def test_wrong_effective_settings_are_rejected(bundle):
    root, settings = bundle
    with pytest.raises(BundleInvalid):
        verify_bundle(root, {**settings, "years": [2021, 2025]})


@pytest.mark.parametrize("reference", [
    "missing.css",
    "../outside.txt",
    "%2e%2e/outside.txt",
    "/outside.txt",
    "file:///etc/passwd",
    "javascript:alert(1)",
])
def test_invalid_references_are_rejected(bundle, reference):
    root, settings = bundle
    (root.parent / "outside.txt").write_text("outside")
    (root / "report.html").write_text(f'<a href="{reference}">Link</a>')
    with pytest.raises(BundleInvalid):
        verify_bundle(root, settings)


def test_symlink_is_rejected(bundle):
    root, settings = bundle
    (root / "linked.html").symlink_to(root / "methods.html")
    with pytest.raises(BundleInvalid):
        verify_bundle(root, settings)


def test_local_asset_and_external_reference_are_allowed(bundle):
    root, settings = bundle
    (root / "asset.css").write_text("body { color: black; }")
    (root / "report.html").write_text(
        '<link href="asset.css" rel="stylesheet">'
        '<a href="https://example.org/">Source</a>'
    )
    assert "asset.css" in verify_bundle(root, settings)["files"]


def test_base_element_is_rejected(bundle):
    root, settings = bundle
    (root / "report.html").write_text('<base href="https://example.org/">')
    with pytest.raises(BundleInvalid):
        verify_bundle(root, settings)


def test_malformed_json_is_rejected(bundle):
    root, settings = bundle
    (root / "provenance.json").write_text("{")
    with pytest.raises(BundleInvalid):
        verify_bundle(root, settings)
