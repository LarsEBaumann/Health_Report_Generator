"""Shared logic for the Quarto reports. Both reports read the same cleaned table
(results/harmonised.csv), so their numbers always agree."""
import calendar
import json
import statistics
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots

# Embed the chart library in the report itself, so charts also show without internet access
# (the default loads it from a CDN, which leaves the plots blank when offline or blocked).
pio.renderers.default = "notebook"

RESULTS = Path(__file__).resolve().parent.parent / "results"
COLUMNS = ["topic", "source_system", "measure", "period", "period_type", "place", "place_type", "age_group",
           "sex", "breakdown", "value", "pop", "incValue", "is_stat_row", "year"]

# topic -> (label, group). Topics not listed (lab tests, wastewater) are not disease series.
DISEASES = {
    "influenza": ("Influenza", "Respiratory"),
    "influenza-like_illness": ("Flu-like illness (GP visits)", "Respiratory"),
    "covid19": ("COVID-19", "Respiratory"),
    "acute_respiratory_infection": ("Acute respiratory infection (GP visits)", "Respiratory"),
    "campylobacteriosis": ("Campylobacter", "Food-borne"),
    "ehec": ("EHEC", "Food-borne"),
    "shigellosis": ("Shigellosis", "Food-borne"),
    "hepatitis_a": ("Hepatitis A", "Food-borne"),
    "hepatitis_e": ("Hepatitis E", "Food-borne"),
    "chlamydiosis": ("Chlamydia", "Sexually / blood transmitted"),
    "gonorrhea": ("Gonorrhoea", "Sexually / blood transmitted"),
    "hiv": ("HIV", "Sexually / blood transmitted"),
    "aids": ("AIDS", "Sexually / blood transmitted"),
    "hepatitis_b": ("Hepatitis B", "Sexually / blood transmitted"),
    "hepatitis_c": ("Hepatitis C", "Sexually / blood transmitted"),
    "lyme_borreliosis": ("Lyme disease", "Tick-borne"),
}
CANTONS = {
    "AG": "Aargau", "AI": "Appenzell I.Rh.", "AR": "Appenzell A.Rh.", "BE": "Bern", "BL": "Basel-Landschaft",
    "BS": "Basel-Stadt", "FR": "Fribourg", "GE": "Geneva", "GL": "Glarus", "GR": "Graubünden", "JU": "Jura",
    "LU": "Lucerne", "NE": "Neuchâtel", "NW": "Nidwalden", "OW": "Obwalden", "SG": "St. Gallen",
    "SH": "Schaffhausen", "SO": "Solothurn", "SZ": "Schwyz", "TG": "Thurgau", "TI": "Ticino", "UR": "Uri",
    "VD": "Vaud", "VS": "Valais", "ZG": "Zug", "ZH": "Zurich",
}
FINEST = ["iso_week", "week", "month", "year"]
LEVELS = {"high": "▲▲ Record high", "elevated": "▲ Above normal", "normal": "● Normal", "low": "▼ Low",
          "unknown": "○ No baseline"}
LEVEL_ORDER = list(LEVELS)

BLUE, BAND, MUTED, INK, GRID = "#2a78d6", "#e1e0d9", "#898781", "#0b0b0b", "#e1e0d9"
MEDIAN = "#245b8a"  # dashed median line: blue, distinct from the red/yellow/green status colours and the grey band
LAYOUT = dict(template="simple_white", font=dict(family="system-ui, sans-serif", size=13, color=INK),
              margin=dict(l=50, r=20, t=40, b=40), hovermode="x unified",
              legend=dict(orientation="h", y=1.12, x=0))


def label(topic: str) -> str:
    return DISEASES[topic][0]


def load() -> pd.DataFrame:
    return pd.read_csv(RESULTS / "harmonised.csv", usecols=COLUMNS, low_memory=False)


def totals(d: pd.DataFrame) -> pd.DataFrame:
    """All ages, both sexes, no sub-type split. COVID-19 only exists as positive tests."""
    return d[(d.age_group == "all") & (d.sex == "all")
             & (d.breakdown.isna() | (d.breakdown == "testResult=positive"))]


def national(d: pd.DataFrame) -> pd.DataFrame:
    """National totals: Switzerland + Liechtenstein (CHFL) where published, otherwise Switzerland (CH)."""
    n = totals(d)
    n = n[((n.place == "CHFL") & (n.place_type == "CHFL")) | ((n.place == "CH") & (n.place_type == "country"))]
    has_chfl = n[n.place == "CHFL"].topic.unique()
    return n[(n.place == "CHFL") | ~n.topic.isin(has_chfl)]


def count_measure(rows: pd.DataFrame) -> str:
    return "cases" if (rows.measure == "cases").any() else "consultations"


def split(period: str) -> tuple[int, str]:
    year, _, sub = str(period).partition("-")
    return int(year), sub


def period_label(period: str) -> str:
    year, sub = split(period)
    if sub.startswith("W"):
        return f"week {int(sub[1:])}, {year}"
    if sub.startswith("M"):
        return f"{calendar.month_name[int(sub[1:])]} {year}"
    return str(year)


def short_label(period: str) -> str:
    year, sub = split(period)
    if sub.startswith("W"):
        return f"W{int(sub[1:])} {year}"
    if sub.startswith("M"):
        return f"{calendar.month_abbr[int(sub[1:])]} {year}"
    return str(year)


def series(d: pd.DataFrame, topic: str, period_type: str | None = None) -> pd.DataFrame:
    """National time series of one disease with its historical band (min, median, max).

    The band is FOPH's own where published; otherwise the same week or month in the previous 5 years.
    """
    nat = national(d[d.topic == topic])
    measure = count_measure(nat)
    counts = nat[nat.measure == measure]
    period_type = period_type or next(t for t in FINEST if (counts.period_type == t).any())
    s = (counts[counts.period_type == period_type].dropna(subset=["value"])
         .drop_duplicates("period").sort_values("period").set_index("period")[["value", "incValue"]])
    stats = nat[(nat.period_type == period_type) & nat.measure.str.match(r"(min|median|max)_value_")]
    if len(stats):
        band = stats.assign(stat=stats.measure.str.split("_").str[0]).pivot_table(
            index="period", columns="stat", values="value", aggfunc="first")
        kind = stats.measure.iloc[0].rsplit("_", 1)[1].replace("y", "-year range (FOPH)")
    else:
        by_key = {split(p): v for p, v in s.value.items()}
        rows = {}
        for p in s.index:
            year, sub = split(p)
            past = [by_key[(year - k, sub)] for k in range(1, 6) if (year - k, sub) in by_key]
            if len(past) >= 3:
                rows[p] = dict(min=min(past), median=statistics.median(past), max=max(past))
        band = pd.DataFrame.from_dict(rows, orient="index")
        kind = "5-year range (computed)"
    s = s.join(band.reindex(columns=["min", "median", "max"]))
    s.attrs.update(topic=topic, measure=measure, period_type=period_type, baseline=kind,
                   geography=nat.place.iloc[0], source=nat.source_system.iloc[0])
    return s


def level(value: float, lo: float, med: float, hi: float) -> str:
    """FOPH's band includes the current value, so touching the max means a record for this time of year."""
    if pd.isna(med):
        return "unknown"
    if value >= hi and value > med:
        return "high"
    if value >= med * 1.2 and value - med >= 3:
        return "elevated"
    if value <= lo and value < med:
        return "low"
    return "normal"


def pct_change(new: float, old: float | None) -> float | None:
    return None if old is None or pd.isna(old) or old == 0 else (new - old) / old * 100


def status(d: pd.DataFrame) -> pd.DataFrame:
    """One row per disease: latest value, comparison with the historical band, change and year to date."""
    rows = []
    for topic, (name, group) in DISEASES.items():
        s = series(d, topic)
        latest, last = s.index[-1], s.iloc[-1]
        year, sub = split(latest)
        if sub.startswith("W"):
            change = pct_change(s.value.iloc[-4:].sum(), s.value.iloc[-8:-4].sum())
            change_basis = "last 4 weeks vs previous 4"
        else:
            previous = f"{year - 1}-{sub}" if sub else str(year - 1)
            change = pct_change(last.value, s.value.get(previous))
            change_basis = "vs same period last year"
        ytd = ytd_prev = None
        if sub:
            ytd = s.value[[split(p)[0] == year for p in s.index]].sum()
            ytd_prev = s.value[[split(p)[0] == year - 1 and split(p)[1] <= sub for p in s.index]].sum()
        rows.append(dict(
            topic=topic, disease=name, group=group, measure=s.attrs["measure"], geography=s.attrs["geography"],
            period=latest, period_label=period_label(latest), frequency=s.attrs["period_type"],
            value=last.value, incidence=last.incValue, min=last["min"], median=last["median"], max=last["max"],
            ratio=last.value / last["median"] if last["median"] else None,
            level=level(last.value, last["min"], last["median"], last["max"]), baseline=s.attrs["baseline"],
            change_pct=change, change_basis=change_basis, ytd=ytd, ytd_prev=ytd_prev,
            ytd_pct=pct_change(ytd, ytd_prev) if ytd is not None else None))
    out = pd.DataFrame(rows)
    out["level_label"] = out.level.map(LEVELS)
    return out.sort_values(["level", "ratio"], key=lambda c: c.map(LEVEL_ORDER.index) if c.name == "level" else -c.fillna(0)
                           ).reset_index(drop=True)


def versus_usual(ratio: float | None) -> str:
    if ratio is None or pd.isna(ratio):
        return "no historical comparison"
    if ratio >= 1.95:
        return f"about {ratio:.0f} times the usual level"
    if ratio >= 1.15:
        return f"about {round((ratio - 1) * 20) * 5}% above the usual level"
    if ratio > 0.87:
        return "close to the usual level"
    return f"about {round((1 - ratio) * 20) * 5}% below the usual level"


def regional(d: pd.DataFrame, topic: str) -> tuple[pd.DataFrame, str]:
    """Cases and incidence per canton: latest full year, or the last 4 weeks for weekly diseases."""
    t = totals(d[(d.topic == topic) & (d.place_type == "canton") & (d.place != "unknown")])
    t = t[t.measure == "cases"].dropna(subset=["value"])
    if t.empty:
        return t, ""
    if (t.period_type == "year").any():
        t = t[t.period_type == "year"]
        periods = [t.period.max()]
        when = str(periods[0])
    else:
        t = t[t.period_type == "iso_week"]
        periods = sorted(t.period.unique())[-4:]
        when = f"weeks {split(periods[0])[1][1:].lstrip('0')}-{split(periods[-1])[1][1:].lstrip('0')}, {split(periods[-1])[0]}"
    out = (t[t.period.isin(periods)].groupby("place").agg(cases=("value", "sum"), incidence=("incValue", "sum"))
           .reset_index().sort_values("incidence", ascending=False))
    out["canton"] = out.place.map(CANTONS)
    return out, when


def by_age(d: pd.DataFrame, topic: str) -> tuple[pd.DataFrame, str]:
    """Incidence per age group for the latest full year (or FOPH's long-term mean where that is all there is)."""
    n = d[(d.topic == topic) & (d.sex == "all") & ~d.age_group.isin(["all", "unknown"])
          & d.place.isin(["CHFL", "CH"]) & d.place_type.isin(["CHFL", "country"])
          & (d.breakdown.isna() | (d.breakdown == "testResult=positive"))].dropna(subset=["incValue"])
    counts = n[n.measure.isin(["cases", "consultations"])]
    if (counts.period_type == "year").any():
        rows, basis = counts[counts.period_type == "year"], "reported"
        rows = rows[rows.period == rows.period.max()]
    elif len(counts):
        full_year = counts.year.max() - 1
        rows, basis = counts[(counts.year == full_year) & counts.period_type.isin(["iso_week", "week"])], "sum of weekly incidence"
    else:
        rows, basis = n[n.measure.str.endswith("_mean") & (n.period_type == "year")], "FOPH long-term mean"
        rows = rows[rows.period == rows.period.max()]
    if rows.empty:
        return rows, ""
    out = rows.groupby("age_group").incValue.sum().reset_index()
    out = out.sort_values("age_group", key=lambda c: c.str.extract(r"(\d+)")[0].astype(int))
    return out, f"{rows.year.max()}, {basis}"


# ------------------------------------------------------------------ charts
def trend_figure(s: pd.DataFrame, points: int | None = None, height: int = 300) -> go.Figure:
    """One series against its historical min-max band and median."""
    points = points or {"iso_week": 104, "week": 104, "month": 48, "year": 20}[s.attrs["period_type"]]
    attrs = s.attrs
    s = s.iloc[-points:].rename(index=short_label)
    s.attrs = attrs
    name = label(s.attrs["topic"])
    unit = "Reported cases" if s.attrs["measure"] == "cases" else "Estimated GP consultations"
    # a band far above the series (pandemic years) would flatten the line, so cap the axis
    top = max(s.value.max(), min(s["max"].max(), 1.5 * s.value.max())) * 1.08
    fig = go.Figure()
    if s["max"].notna().any():
        fig.add_scatter(x=s.index, y=s["max"], mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip")
        fig.add_scatter(x=s.index, y=s["min"], mode="lines", line=dict(width=0), fill="tonexty", fillcolor=BAND,
                        name=f"Min-max, {s.attrs['baseline']}", hoverinfo="skip")
        fig.add_scatter(x=s.index, y=s["median"], mode="lines", line=dict(color=MEDIAN, width=2, dash="dash"),
                        name="Median")
    fig.add_scatter(x=s.index, y=s.value, mode="lines", line=dict(color=BLUE, width=2), name=unit)
    fig.add_scatter(x=[s.index[-1]], y=[s.value.iloc[-1]], mode="markers+text", marker=dict(color=BLUE, size=9),
                    text=[f"{s.value.iloc[-1]:,.0f}"], textposition="middle right", showlegend=False,
                    hoverinfo="skip", cliponaxis=False)
    fig.update_layout(**LAYOUT, height=height, title=dict(text=name, font=dict(size=15)))
    fig.update_layout(margin=dict(r=60))
    fig.update_yaxes(range=[0, top], gridcolor=GRID, showgrid=True, rangemode="tozero")
    fig.update_xaxes(nticks=6, type="category")
    return fig


def bar_figure(frame: pd.DataFrame, x: str, y: str, title: str, x_title: str, height: int = 320) -> go.Figure:
    """Horizontal bars, one hue, largest at the top."""
    frame = frame.iloc[::-1]
    fig = go.Figure(go.Bar(x=frame[x], y=frame[y], orientation="h", marker=dict(color=BLUE),
                           hovertemplate="%{y}: %{x:,.1f}<extra></extra>"))
    fig.update_layout(**LAYOUT, height=height, title=dict(text=title, font=dict(size=15)), bargap=0.35)
    fig.update_layout(hovermode="closest")
    fig.update_xaxes(title=x_title, gridcolor=GRID, showgrid=True)
    return fig


def small_multiples(frames: dict[str, pd.Series], y_title: str, cols: int = 4, kind: str = "line") -> go.Figure:
    """One small panel per disease, each with its own y-axis (levels differ by orders of magnitude)."""
    names = list(frames)
    n_rows = -(-len(names) // cols)
    fig = make_subplots(rows=n_rows, cols=cols, subplot_titles=names, vertical_spacing=0.34 / n_rows + 0.03,
                        horizontal_spacing=0.06)
    for i, name in enumerate(names):
        s = frames[name]
        trace = (go.Bar(x=s.index, y=s.values, marker=dict(color=BLUE)) if kind == "bar"
                 else go.Scatter(x=s.index, y=s.values, mode="lines", line=dict(color=BLUE, width=2)))
        trace.update(name=name, hovertemplate="%{x}: %{y:,.1f}<extra>" + name + "</extra>")
        fig.add_trace(trace, row=i // cols + 1, col=i % cols + 1)
    fig.update_layout(**LAYOUT, height=210 * n_rows + 40, showlegend=False)
    fig.update_layout(hovermode="closest", margin=dict(t=80))
    fig.update_yaxes(rangemode="tozero", gridcolor=GRID, showgrid=True, tickfont=dict(size=10))
    fig.update_xaxes(tickfont=dict(size=10))
    fig.update_annotations(font=dict(size=12))
    fig.add_annotation(text=y_title, xref="paper", yref="paper", x=0, y=1.0, yshift=58, showarrow=False,
                       font=dict(size=12, color=MUTED), xanchor="left")
    return fig


MAP_RAMP = ["#cde2fb", "#3987e5", "#0d366b"]  # light to dark blue
# Several colours in one ordered scale: yellow (lowest) through green and teal to purple (highest).
# It gets steadily darker, so it still reads as low-to-high, including for colour-blind readers.
MAP_RAMP_MULTI = ["#fde725", "#7ad151", "#22a884", "#2a788e", "#414487", "#440154"]
MAP_GREY = "#dfe3e6"


def _ramp(share: float, ramp: list[str]) -> str:
    """Colour at `share` (0 to 1) along `ramp`."""
    stops = [tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) for c in ramp]
    pos = min(max(share, 0), 1) * (len(stops) - 1)
    lo = min(int(pos), len(stops) - 2)
    return "#" + "".join(f"{round(stops[lo][k] + (stops[lo + 1][k] - stops[lo][k]) * (pos - lo)):02x}" for k in range(3))


def canton_map(d: pd.DataFrame, ramp: list[str] = MAP_RAMP) -> go.Figure:
    """Map of Switzerland with each canton shaded by cases per 100,000, one disease at a time.

    A menu switches between the diseases that have canton-level data. Cantons with fewer than
    5 cases stay grey, because their rates are unstable. The canton outlines are drawn as plain
    filled shapes (not a web map), so the map also works offline and in the PDF.
    """
    boundaries = json.loads((Path(__file__).resolve().parent / "swiss_cantons.geojson").read_text(encoding="utf-8"))
    squeeze = 0.684  # cos(46.8 deg): one degree of longitude is this much shorter than one of latitude here
    outlines = {}
    for feature in boundaries["features"]:
        geometry = feature["geometry"]
        polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
        xs, ys = [], []
        for polygon in polygons:
            for lon, lat in polygon[0]:  # outer ring
                xs.append(lon * squeeze)
                ys.append(lat)
            xs.append(None)
            ys.append(None)
        outlines[feature["properties"]["code"]] = (xs, ys)
    codes = sorted(outlines)

    layers = []
    for topic in DISEASES:
        regions, when = regional(d, topic)
        if len(regions):
            regions = regions.set_index("place").reindex(codes)
            top = float(regions.incidence.where(regions.cases >= 5).max())
            colours, texts = [], []
            for code, row in zip(codes, regions.itertuples()):
                if row.cases >= 5:
                    colours.append(_ramp(row.incidence / top, ramp))
                    texts.append(f"<b>{CANTONS[code]}</b><br>{row.incidence:,.1f} per 100,000<br>{row.cases:,.0f} cases")
                else:
                    colours.append(MAP_GREY)
                    texts.append(f"<b>{CANTONS[code]}</b><br>fewer than 5 cases")
            layers.append(dict(name=f"{label(topic)} · {when}", colours=colours, texts=texts, top=top,
                               cases=regions.cases.sum()))
    layers.sort(key=lambda layer: -layer["cases"])  # the disease with most cases is shown first
    first = layers[0]

    fig = go.Figure()
    for code, colour, text in zip(codes, first["colours"], first["texts"]):
        xs, ys = outlines[code]
        fig.add_scatter(x=xs, y=ys, mode="lines", fill="toself", fillcolor=colour, line=dict(color="white", width=1),
                        hoveron="fills", hoverinfo="text", text=text, name=CANTONS[code], showlegend=False)
    # invisible point that carries the colour bar
    fig.add_scatter(x=[outlines[codes[0]][0][0]], y=[outlines[codes[0]][1][0]], mode="markers", hoverinfo="skip",
                    showlegend=False,
                    marker=dict(size=0.1, opacity=0, color=[0], cmin=0, cmax=first["top"], showscale=True,
                                colorscale=[[i / (len(ramp) - 1), c] for i, c in enumerate(ramp)],
                                colorbar=dict(title="Cases per<br>100,000", thickness=14, len=0.8)))
    buttons = [dict(label=layer["name"], method="restyle",
                    args=[{"fillcolor": layer["colours"] + [None], "text": layer["texts"] + [None],
                           "marker.cmax": [None] * len(codes) + [layer["top"]]}])
               for layer in layers]
    fig.update_layout(**LAYOUT, height=500,
                      updatemenus=[dict(buttons=buttons, x=0, xanchor="left", y=1.14, yanchor="top",
                                        bgcolor="white", bordercolor="#c3c2b7")])
    fig.update_layout(hovermode="closest", margin=dict(l=0, r=0, t=70, b=10))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False, scaleanchor="x", scaleratio=1)
    return fig


def season_heatmap(d: pd.DataFrame, topic: str) -> go.Figure:
    """Month-by-year heatmap of monthly cases: one hue, light to dark."""
    s = series(d, topic, "month")
    frame = pd.DataFrame({"year": [split(p)[0] for p in s.index], "month": [int(split(p)[1][1:]) for p in s.index],
                          "value": s.value.values})
    grid = frame.pivot(index="year", columns="month", values="value").sort_index(ascending=False)
    fig = go.Figure(go.Heatmap(
        z=grid.values, x=[calendar.month_abbr[m] for m in grid.columns], y=[str(y) for y in grid.index],
        colorscale=[[0, "#cde2fb"], [0.5, "#3987e5"], [1, "#0d366b"]], xgap=2, ygap=2,
        colorbar=dict(title="Cases", thickness=12), hovertemplate="%{x} %{y}: %{z:,.0f}<extra></extra>"))
    fig.update_layout(**LAYOUT, height=380, title=dict(text=label(topic), font=dict(size=15)))
    fig.update_layout(hovermode="closest")
    fig.update_yaxes(type="category")
    return fig
