"""Sections lifted straight out of the rendered report.

The dashboards show the report's own tables and prose, not a second version of them: this
reads `results/site/<report>.html` and hands back the markup Quarto produced. A section
that draws a chart is skipped, because its figure is rebuilt from the report's plotting
code in figures.py; what is served here is the script-free part -- the tables, the methods,
the coverage notes, the limitations and the provenance record.
"""
from __future__ import annotations

import re
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
SITE = PROJECT / "results" / "site"

SECTION = re.compile(r'<section id="([^"]+)" class="level([23])">')
HEADING = re.compile(r"<h[23][^>]*>(.*?)</h[23]>", re.S)
ANCHOR = re.compile(r'<a\b[^>]*class="[^"]*anchor[^"]*"[^>]*>.*?</a>', re.S)
TAGS = re.compile(r"<[^>]+>")

# Where each report section belongs, per audience. Sections not listed are not shown:
# either a chart rebuilds them, or they duplicate a panel.
TABS = {
    "researcher": {
        "current-status-of-every-series": "diseases",
        "table-by-canton": "geography",
        "data-at-a-glance": "methods",
        "data-coverage": "methods",
        "quality-checks": "methods",
        "methods": "methods",
        "limitations": "methods",
        "provenance": "methods",
    },
    "health_institution": {
        "situation-at-a-glance": "summary",
        "burden-this-year-compared-with-last-year": "priority",
        "how-to-read-this-report": "reliability",
        "provenance": "reliability",
    },
}

_cache: dict[str, tuple[float, list]] = {}


def _bodies(html: str):
    """Each section's id, level and inner markup, matched by counting nested tags."""
    for match in SECTION.finditer(html):
        start = match.end()
        depth, index = 1, start
        while depth and index < len(html):
            nxt = re.compile(r"</?section\b").search(html, index)
            if not nxt:
                break
            depth += 1 if nxt.group(0) == "<section" else -1
            index = nxt.end()
        yield match.group(1), int(match.group(2)), html[start:index - len("</section>")]


def _title(body: str) -> str:
    found = HEADING.search(body)
    if not found:
        return ""
    return TAGS.sub("", ANCHOR.sub("", found.group(1))).strip()


def sections(report: str, audience: str) -> list[dict]:
    """The report's script-free sections, each tagged with the tab that should show it."""
    source = SITE / f"{report}.html"
    if not source.exists():
        return []
    stamp = source.stat().st_mtime
    key = f"{report}:{audience}"
    cached = _cache.get(key)
    if cached and cached[0] == stamp:
        return cached[1]

    wanted = TABS.get(audience, {})
    html = source.read_text(encoding="utf-8")
    out = []
    for sid, _level, body in _bodies(html):
        if sid not in wanted or "<script" in body:
            # A section with a script draws a chart; figures.py rebuilds that one.
            continue
        out.append({
            "id": sid,
            "title": _title(body),
            "tab": wanted[sid],
            # The heading becomes the panel's own title, so it is not repeated inside.
            "html": HEADING.sub("", body, count=1).strip(),
        })
    order = list(wanted)
    out.sort(key=lambda s: order.index(s["id"]))
    _cache[key] = (stamp, out)
    return out
