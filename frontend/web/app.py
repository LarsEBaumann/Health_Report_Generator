"""A local web page for generating reports: pick an audience and diseases, get a report.

Runs entirely on this machine. No GitHub account, token or Actions run, and no R: the
reports it builds are the Python/Quarto ones in reports/. It is a thin layer over
frontend/local_build.py, which is also what the Marimo interface uses.

Served by Starlette and uvicorn, which are already dependencies, so this adds nothing to
install. Start it with `python run.py web`.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, Response
from starlette.routing import Route

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import local_build  # noqa: E402  (the path above makes this importable)
from frontend.web import data, figures, sections  # noqa: E402

HERE = Path(__file__).resolve().parent
PAGE = HERE / "page.html"
PROJECT = local_build.PROJECT
FULL_SITE = PROJECT / "results" / "site"

def page(request):
    return HTMLResponse(PAGE.read_text(encoding="utf-8"))


def full_reports():
    """The whole-data reports the pipeline builds, named by workflow/config.yaml.

    Globbing results/site would also pick up one-off files left there by hand.
    """
    config = PROJECT / "workflow" / "config.yaml"
    names = []
    inside = False
    for line in config.read_text(encoding="utf-8").splitlines():
        if line.startswith("quarto_reports:"):
            inside = True
        elif inside and line.strip().startswith("- "):
            names.append(line.strip()[2:].strip())
        elif inside and line and not line.startswith((" ", "-", "#")):
            break
    return [f"{name}.html" for name in names if (FULL_SITE / f"{name}.html").exists()]


def previous_reports():
    """Reports generated earlier, newest first, so a build is never lost on reload."""
    if not local_build.SELECTED_DIR.is_dir():
        return []
    files = sorted(local_build.SELECTED_DIR.glob("*.html"),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    return [{"name": p.name, "url": f"/report/{p.name}",
             "built": time.strftime("%Y-%m-%d %H:%M", time.localtime(p.stat().st_mtime))}
            for p in files[:12]]


async def render(request):
    body = await request.json()
    audience = str(body.get("audience", ""))
    # The page selects diseases (topics); the dataset ids behind them are also accepted.
    wanted_topics = [str(t) for t in body.get("topics", [])]
    chosen = [str(d) for d in body.get("datasets", [])]
    if not wanted_topics and not chosen:
        return JSONResponse({"error": "Select at least one disease."}, status_code=400)

    bundle = local_build.bundle()
    if bundle is None:
        return JSONResponse({"error": "No local build found. Run `python run.py` first."},
                            status_code=503)
    started = time.monotonic()
    try:
        topics = wanted_topics or local_build.topics_for(bundle, chosen)
        # Rendering takes a minute or two, so it runs off the event loop and the page
        # keeps responding while it works.
        existing = local_build.SELECTED_DIR / (
            f"{audience}-{local_build.fingerprint(audience, local_build.report_for(audience), topics)}.html")
        cached = existing.exists()
        output = await run_in_threadpool(local_build.render, audience, topics)
    except (ValueError, RuntimeError) as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    return JSONResponse({
        "url": f"/report/{output.name}",
        "name": output.name,
        "topics": topics,
        "seconds": round(time.monotonic() - started, 1),
        "reused": cached,
        "previous": previous_reports(),
    })


def context(request):
    """Who the audiences are, what each one's panels and parameters are, and what exists."""
    return JSONResponse({
        "audiences": data.audiences(local_build.LOCAL_REPORTS),
        "filters": data.filters(),
        "summary": data.summary(),
        "full_reports": full_reports(),
        "previous": previous_reports(),
    })


def overview(request):
    """Every figure one audience's dashboards show, aggregated from its analysis bundle."""
    audience = request.path_params["audience"]
    if audience not in data.stakeholder_ids():
        return JSONResponse({"error": f"no such audience: {audience}"}, status_code=404)
    found = data.payload(audience, local_build.LOCAL_REPORTS)
    if found is None:
        return JSONResponse(
            {"error": "No analysis tables for this audience yet. Run `python run.py` first."},
            status_code=503,
        )
    return JSONResponse(found)


def provenance(request):
    """The record a rendered report embeds: checksums, snapshot, tools, code versions.

    Looked up by report name in both output directories, so the same call serves a full
    report and one built from a disease selection.
    """
    name = request.path_params["name"]
    for directory in (FULL_SITE, local_build.SELECTED_DIR):
        record = directory / f"provenance_{name}.json"
        # Resolved and checked against the directory, so a crafted name cannot escape it.
        if record.name in {p.name for p in directory.glob("provenance_*.json")}:
            return JSONResponse(json.loads(record.read_text(encoding="utf-8")))
    return JSONResponse({"error": "no provenance record for " + name}, status_code=404)


def charts(request):
    """The report's own charts for one audience, as plotly specifications."""
    audience = request.path_params["audience"]
    found = [a for a in data.audiences(local_build.LOCAL_REPORTS) if a["id"] == audience]
    if not found:
        return JSONResponse({"error": f"no such audience: {audience}"}, status_code=404)
    if data.bundle(audience) is None:
        return JSONResponse({"error": "Run `python run.py` first."}, status_code=503)
    try:
        return JSONResponse({"figures": figures.figures(audience, found[0]["detail"])})
    except Exception as error:  # a chart must never take the whole page down
        return JSONResponse({"error": f"charts could not be built: {error}"}, status_code=500)


def report_sections(request):
    """Tables and prose taken verbatim from the audience's rendered report."""
    audience = request.path_params["audience"]
    report = local_build.LOCAL_REPORTS.get(audience)
    if not report:
        return JSONResponse({"sections": []})
    return JSONResponse({"sections": sections.sections(report, audience)})


def plotly_bundle(request):
    """Served from the installed plotly package, so the page loads nothing remotely."""
    return Response(figures.plotly_js(), media_type="application/javascript",
                    headers={"Cache-Control": "max-age=86400"})


def one_report(request):
    """Serve a generated report. The name is matched against the directory listing, so a
    crafted path cannot escape it."""
    name = request.path_params["name"]
    allowed = {p.name for p in local_build.SELECTED_DIR.glob("*.html")}
    if name not in allowed:
        return JSONResponse({"error": "no such report"}, status_code=404)
    return FileResponse(local_build.SELECTED_DIR / name)


def full_report(request):
    name = request.path_params["name"]
    allowed = {p.name for p in FULL_SITE.glob("*.html")}
    if name not in allowed:
        return JSONResponse({"error": "no such report"}, status_code=404)
    return FileResponse(FULL_SITE / name)


app = Starlette(routes=[
    Route("/", page),
    Route("/api/context", context),
    Route("/api/overview/{audience}", overview),
    Route("/api/render", render, methods=["POST"]),
    Route("/api/figures/{audience}", charts),
    Route("/api/sections/{audience}", report_sections),
    Route("/static/plotly.js", plotly_bundle),
    Route("/api/provenance/{name}", provenance),
    Route("/report/{name}", one_report),
    Route("/full/{name}", full_report),
])
