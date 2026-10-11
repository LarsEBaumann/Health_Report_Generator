import os
import shutil
import subprocess
from pathlib import Path

import pytest

import publish


@pytest.mark.parametrize("html_only", [True, False])
def test_publisher_format_links(tmp_path, monkeypatch, html_only):
    if html_only:
        monkeypatch.setenv("HEALTH_REPORT_HTML_ONLY", "1")
    else:
        monkeypatch.delenv("HEALTH_REPORT_HTML_ONLY", raising=False)

    calls = []
    monkeypatch.setattr(publish, "package", lambda bundle, dest: None)

    def fake_run(command, *, cwd, check, env):
        calls.append((list(command), dict(env)))
        document = Path(command[2]).stem
        (Path(cwd) / f"{document}.html").write_text("<html>Rendered</html>")

    monkeypatch.setattr(publish.subprocess, "run", fake_run)
    publish.render(tmp_path, tmp_path / "out" / "report.html", "html")

    assert len(calls) == 2
    for command, env in calls:
        assert ("format-links:false" in command) == html_only
        assert env["HEALTH_REPORT_PDF_AVAILABLE"] == (
            "0" if html_only else "1"
        )


@pytest.mark.skipif(shutil.which("Rscript") is None, reason="R unavailable")
@pytest.mark.parametrize("available", ["0", "1"])
@pytest.mark.parametrize("methods", [False, True])
def test_r_navigation_matches_available_outputs(available, methods):
    code = f"""
source('report_helpers.R')
b <- list(cfg=list(geography='CHFL'))
cat(report_navigation(b, methods={'TRUE' if methods else 'FALSE'}))
"""
    result = subprocess.run(
        ["Rscript", "-e", code],
        cwd=publish.HERE / "templates",
        env={**os.environ, "HEALTH_REPORT_PDF_AVAILABLE": available},
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    html = result.stdout
    assert ('PDF version' in html) == (available == "1")
    if available == "1":
        assert ('methods.pdf' if methods else 'report.pdf') in html
    assert ('report.html' if methods else 'methods.html') in html
