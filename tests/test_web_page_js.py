"""The explorer page ships hand-written JavaScript, so at least prove it parses.

Quarto bundles a Deno runtime, and Quarto is already a prerequisite for building reports.
Where that runtime cannot be found the test skips rather than failing: it is a guard on the
page, not on the machine.
"""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "frontend" / "web" / "page.html"


def deno() -> Path | None:
    quarto = shutil.which("quarto")
    if not quarto:
        return None
    base = Path(quarto).resolve().parent
    for parent in (base, base.parent):
        for found in (parent / "tools").rglob("deno*"):
            if found.is_file() and found.suffix in ("", ".exe"):
                return found
    return None


def script() -> str:
    blocks = re.findall(r"<script>(.*?)</script>", PAGE.read_text(encoding="utf-8"), re.S)
    assert blocks, "the page has no script block"
    return blocks[-1]


def test_page_script_parses():
    runtime = deno()
    if runtime is None:
        pytest.skip("no Deno runtime found next to Quarto")
    # `new Function` parses without running, so no DOM is needed.
    program = (
        "const src = await Deno.readTextFile(Deno.args[0]);"
        "try { new Function(src); } catch (e) { console.log(e.message); Deno.exit(1); }"
    )
    source = ROOT / "frontend" / "web" / "_page_script_check.js"
    source.write_text(script(), encoding="utf-8")
    try:
        done = subprocess.run([str(runtime), "eval", "--no-check", program, str(source)],
                              capture_output=True, text=True, cwd=ROOT)
    finally:
        source.unlink(missing_ok=True)
    assert done.returncode == 0, done.stdout + done.stderr


def test_page_has_no_remote_resources():
    """The page must work offline; the SVG xmlns is a namespace, not a fetch."""
    body = PAGE.read_text(encoding="utf-8")
    remote = re.findall(r"""(?:src|href)\s*=\s*["']((?:https?:)?//[^"']+)""", body)
    assert not remote, remote


def test_report_reader_and_provenance_are_wired():
    """The report detail is shown in the page, not only linked."""
    body = PAGE.read_text(encoding="utf-8")
    for needed in ("<iframe", "viewerHTML", "provHTML", "/api/provenance/", "data-view"):
        assert needed in body, needed
