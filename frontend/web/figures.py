"""The dashboards' charts, produced by the reports' own plotting code.

Nothing here draws anything. It calls reports/shared/helpers.py -- the module the Quarto
reports use -- so a chart on a dashboard is the same chart, from the same data, with the
same styling as the one in the rendered report. If a report's chart changes, this follows.

Which charts an audience gets follows its `detail_level`: a monitoring audience is shown
what is above its usual level, a technical one is shown everything, and a plain-language
one is shown the long-term picture without the diagnostic detail.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
SHARED = PROJECT / "reports" / "shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

_cache: dict[str, list] = {}
# Where each kind of chart belongs, per audience. The researcher's tabs follow its report's
# argument; every other audience uses the generic layout.
TABS_OF = {
    "researcher": {"map": "geography", "season": "geography",
                   "annual": "diseases", "ages": "diseases"},
    "health_institution": {"map": "regional", "season": "regional", "annual": "summary",
                           "ages": "summary", "watch": "priority", "mover": "priority"},
    "public": {"map": "region", "season": "diseases", "annual": "diseases",
               "ages": "diseases", "watch": "happening", "mover": "happening"},
    "_default": {"map": "overview", "season": "trends", "annual": "trends",
                 "ages": "trends", "watch": "overview", "mover": "overview"},
}


def tab_ids(audience: str) -> list:
    """The tabs this audience actually has, so no chart is routed into a missing one."""
    from frontend.web import data
    config = data.STAKEHOLDERS / f"{audience}.json"
    if not config.exists():
        return []
    outputs = json.loads(config.read_text(encoding="utf-8")).get("outputs", [])
    return [tab["id"] for tab in data.tabs_for(audience, outputs)]


def tab_of(audience: str, kind: str) -> str:
    """The tab a chart belongs on.

    Falls back to the generic layout, and then to the audience's first tab: a chart that
    has nowhere to go would otherwise be built and never shown.
    """
    table = TABS_OF.get(audience, TABS_OF["_default"])
    chosen = table.get(kind) or TABS_OF["_default"].get(kind, "overview")
    available = tab_ids(audience)
    if available and chosen not in available:
        return available[0]
    return chosen
# Diseases FOPH publishes monthly with a clear season; the report hard-codes the same set.
SEASONAL = ["influenza", "campylobacteriosis", "ehec", "lyme_borreliosis"]


def plotly_js() -> str:
    """The plotly bundle that ships with the Python package, so the page needs no CDN."""
    from plotly.offline import get_plotlyjs
    return get_plotlyjs()


def _fig(figure, fid, title, note, tab):
    # to_plotly_json leaves numpy types in place; the JSON encoder plotly ships handles them.
    from plotly.utils import PlotlyJSONEncoder
    return {"id": fid, "title": title, "note": note, "tab": tab,
            "spec": json.loads(json.dumps(figure.to_plotly_json(), cls=PlotlyJSONEncoder))}


def build(audience: str, detail: str) -> list[dict]:
    """Charts for one audience, in the order they should appear."""
    import helpers as h

    frame = h.load()
    out = []

    # Where cases are, on the map the report draws. Every audience gets this.
    out.append(_fig(h.canton_map(frame), "map", "Cases by canton",
                    "Choose a disease above the map. Grey cantons had fewer than 5 cases.",
                    tab_of(audience, "map")))

    # The long-term picture, one small panel per disease.
    annual = {}
    for topic in h.DISEASES:
        rows = h.series(frame, topic, "year")
        if len(rows):
            annual[h.label(topic)] = rows.incValue.rename(index=int)
    if annual:
        out.append(_fig(h.small_multiples(annual, "Cases or consultations per 100,000 per year"),
                        "annual", "Long-term trends",
                        "Annual rate per 100,000 from the first published year. Each panel has its own scale.",
                        tab_of(audience, "annual")))

    table = h.status(frame)

    if detail == "monitoring":
        # What needs attention now: every indicator above its usual level, newest first.
        above = table[table.level.isin(["high", "elevated"])]
        for row in above.itertuples():
            series = h.series(frame, row.topic)
            out.append(_fig(h.trend_figure(series), f"watch-{row.topic}",
                            f"{row.disease}: {row.level_label}",
                            f"{row.period_label}. {h.versus_usual(row.ratio)}",
                            tab_of(audience, "watch")))
        if not len(above):
            out.append(_fig(h._no_data("No indicator is above its usual level."),
                            "watch-none", "Nothing above its usual level",
                            "Every monitored indicator sits within its comparison window.",
                            tab_of(audience, "watch")))

    if detail == "full":
        # The diagnostic detail: seasonality and who is affected.
        for topic in h.covered(SEASONAL):
            out.append(_fig(h.season_heatmap(frame, topic), f"season-{topic}",
                            f"Seasonality: {h.label(topic)}",
                            "Monthly cases by year. Darker means more cases.",
                            tab_of(audience, "season")))
        ages = {}
        for topic in h.DISEASES:
            rows, basis = h.by_age(frame, topic)
            if len(rows):
                ages[f"{h.label(topic)}<br><sup>{basis}</sup>"] = rows.set_index("age_group").incValue
        if ages:
            out.append(_fig(h.small_multiples(ages, "Per 100,000", kind="bar"), "ages",
                            "Age distribution",
                            "Rate per 100,000 by age group. Age bands differ between disease families.",
                            tab_of(audience, "ages")))

    if detail == "plain_language":
        # The two or three series that moved most, with their comparison window.
        movers = table.dropna(subset=["change_pct"]).reindex(
            table.change_pct.abs().sort_values(ascending=False).index).head(3)
        for row in movers.itertuples():
            out.append(_fig(h.trend_figure(h.series(frame, row.topic)), f"mover-{row.topic}",
                            f"{row.disease}",
                            f"{row.period_label}. Change {row.change_pct:+.0f}% {row.change_basis}.",
                            tab_of(audience, "mover")))
    return out


def figures(audience: str, detail: str) -> list[dict]:
    """Cached per audience: building these reads the cleaned table and draws every chart."""
    key = f"{audience}:{detail}"
    if key not in _cache:
        _cache[key] = build(audience, detail)
    return _cache[key]
