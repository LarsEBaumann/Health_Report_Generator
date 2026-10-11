"""Verify private generated report bundles before publication."""

import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


class BundleInvalid(ValueError):
    """Generated artifacts fail the publication contract."""


class References(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.urls = []

    def handle_starttag(self, tag, attrs):
        if tag == "base":
            raise BundleInvalid("HTML base elements are not supported.")
        for name, value in attrs:
            if name in ("href", "src", "poster") and value:
                self.urls.append(value)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)


def _json_object(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise BundleInvalid("Invalid JSON artifact.") from exc
    if type(value) is not dict:
        raise BundleInvalid("JSON artifact must be an object.")
    return value


def _check_reference(root, page, reference):
    try:
        parts = urlsplit(reference.strip())
    except ValueError as exc:
        raise BundleInvalid("Invalid resource URL.") from exc

    if parts.scheme.lower() in ("http", "https", "data", "mailto", "tel"):
        return
    if parts.scheme or parts.netloc:
        raise BundleInvalid("Unsupported resource URL scheme or host.")
    if not parts.path:
        return

    path = unquote(parts.path)
    if path.startswith("/") or "\\" in path or "\x00" in path:
        raise BundleInvalid("Unsupported local resource path.")

    try:
        target = (page.parent / path).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise BundleInvalid("Local resource is missing or invalid.") from exc
    if not target.is_relative_to(root) or not target.is_file():
        raise BundleInvalid("Local resource escapes bundle or is not a file.")


def verify_bundle(directory, expected_settings):
    """Return verified file hashes; input must be a private stable workspace."""
    directory = Path(directory)
    if directory.is_symlink():
        raise BundleInvalid("Bundle root cannot be a symlink.")
    root = directory.resolve(strict=True)
    if not root.is_dir():
        raise BundleInvalid("Bundle root must be a directory.")

    files = []
    for path in root.rglob("*"):
        if path.is_symlink():
            raise BundleInvalid("Bundle cannot contain symlinks.")
        if path.is_dir():
            continue
        if not path.is_file():
            raise BundleInvalid("Bundle contains a non-regular entry.")
        files.append(path)

    for name in (
        "report.html", "methods.html",
        "provenance.json", "request_provenance.json",
    ):
        path = root / name
        if not path.is_file() or path.stat().st_size == 0:
            raise BundleInvalid("Core artifact missing or empty.")

    provenance = _json_object(root / "provenance.json")
    effective = provenance.get("effective_parameters")
    if type(effective) is not dict:
        raise BundleInvalid("Effective parameters missing.")

    for key, value in expected_settings.items():
        if key != "id" and (key not in effective or effective[key] != value):
            raise BundleInvalid("Effective settings differ from request.")

    if not re.fullmatch(r"custom_[a-f0-9]{12}", str(effective.get("id", ""))):
        raise BundleInvalid("Unexpected custom report identifier.")

    request_provenance = _json_object(root / "request_provenance.json")
    cache_key = request_provenance.get("cache_key")
    if type(cache_key) is not str or not re.fullmatch(r"[a-f0-9]{64}", cache_key):
        raise BundleInvalid("Invalid cache identity.")

    for page in files:
        if page.suffix.lower() == ".html":
            parser = References()
            parser.feed(page.read_text(encoding="utf-8"))
            parser.close()
            for reference in parser.urls:
                _check_reference(root, page, reference)

    hashes = {}
    for path in sorted(files):
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        hashes[path.relative_to(root).as_posix()] = digest.hexdigest()

    return {"cache_key": cache_key, "files": hashes}
