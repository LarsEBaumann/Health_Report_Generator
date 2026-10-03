#!/usr/bin/env python3
"""
report.py - build a standalone HTML report for one stakeholder from the harmonised table.

Usage: python report.py --stakeholder config/stakeholders/public_health_expert.json --out out/
Writes out/report_<id>.html and out/report_<id>_trace.csv (every number -> source file + row).
"""
import argparse, base64, html, io, json
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
COL = {"viral": "#c2410c", "bacterial": "#0f766e", "syndromic": "#6b7280", "ref": "#9ca3af"}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.alpha": .25})


def fig_b64(fig):
    buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=150, bbox_inches="tight"); plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def pct(a, b):
    return None if (a is None or b is None or pd.isna(a) or pd.isna(b) or a == 0) else (b - a) / a * 100


def fmt_pct(x):
    return "–" if x is None or pd.isna(x) else f"{x:+.0f}%"


def select_series(d, cfg, classes):
    """Capability check + selection of one national yearly series per dataset. Data-agnostic."""
    y0, y1 = cfg["years"]; ref = cfg.get("reference_year")
    used, skipped, trace = [], [], []
    for ds, g in d.groupby("dataset_id"):
        topic = g.topic.iloc[0]
        cls = classes.get(topic, {}).get("pathogen_class", "unclassified")
        base = g[g.is_total & ~g.is_stat_row & g.value.notna()]
        if base.empty:
            skipped.append((ds, topic, cls, "no total rows with values")); continue
        meas = next((m for m in cfg["measures_preferred"] if m in set(base.measure)), None)
        if meas is None:
            skipped.append((ds, topic, cls, f"no count measure (has: {', '.join(sorted(set(base.measure))[:4])})")); continue
        if cls == "surveillance_signal":
            skipped.append((ds, topic, cls, "surveillance signal (positivity / viral load), not comparable to case counts")); continue
        b = base[base.measure == meas]
        nat_place = next((p for p in ["CHFL", "CH"] if p in set(b.place)), None)
        if nat_place is None:
            skipped.append((ds, topic, cls, "no national total")); continue
        b = b[b.place == nat_place]
        if "year" in set(b.period_type):
            yb = b[b.period_type == "year"]
            agg = "reported yearly total"
        elif "month" in set(b.period_type):
            yb = b[b.period_type == "month"]; agg = "sum of monthly values"
        else:
            skipped.append((ds, topic, cls, f"no yearly/monthly data (has {', '.join(set(b.period_type))})")); continue
        yb = yb[yb.year.between(min(y0, ref or y0), y1)]
        if yb.year.nunique() < (y1 - y0 + 1) * .6:
            skipped.append((ds, topic, cls, f"too few years in {y0}-{y1}")); continue
        s = yb.groupby("year").agg(value=("value", "sum"), pop=("pop", "max"))
        s["inc100k"] = s.value / s["pop"] * 1e5
        for _, r in yb.iterrows():
            trace.append(dict(dataset_id=ds, topic=topic, year=int(r.year), value=r.value,
                              source_file=r.source_file, source_row=int(r.source_row)))
        rows = yb.groupby("year").source_row.apply(lambda x: ",".join(map(str, x)))
        used.append(dict(dataset_id=ds, topic=topic, cls=cls, measure=meas, system=g.source_system.iloc[0],
                         label=classes.get(topic, {}).get("label", topic), agg=agg, series=s, rows=rows,
                         source_file=yb.source_file.iloc[0]))
    return used, skipped, pd.DataFrame(trace)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--stakeholder", default=str(HERE / "config/stakeholders/public_health_expert.json"))
    ap.add_argument("--classes", default=str(HERE / "config/pathogen_class.csv"))
    ap.add_argument("--out", default="out")
    a = ap.parse_args(argv)
    out = Path(a.out)
    cfg = json.loads(Path(a.stakeholder).read_text())
    classes = pd.read_csv(a.classes).set_index("topic").to_dict("index")
    d = pd.read_parquet(out / "harmonised.parquet")
    reg = pd.read_csv(out / "datasets.csv")
    checks = pd.read_csv(out / "checks.csv") if (out / "checks.csv").exists() else pd.DataFrame()
    y0, y1 = cfg["years"]; ref = cfg.get("reference_year"); years = list(range(y0, y1 + 1))
    excl = set(cfg.get("exclude_from_group_totals", []))

    used, skipped, trace = select_series(d, cfg, classes)
    main_cls = cfg["classes_in_main_comparison"]
    main = [u for u in used if u["cls"] in main_cls]
    synd = [u for u in used if u["cls"] not in main_cls]

    # ---- group totals & index (excluding configured topics, e.g. COVID-19 which dwarfs everything)
    grp = {}
    for c in main_cls:
        ss = [u["series"].value for u in main if u["cls"] == c and u["topic"] not in excl]
        grp[c] = pd.concat(ss, axis=1).sum(axis=1, min_count=1).reindex([ref] + years) if ss else pd.Series(dtype=float)

    # ---- chart 1: index (base year configurable, default = pre-COVID reference year)
    base_y = cfg.get("index_base_year", ref or y0)
    sens = set(cfg.get("sensitivity_exclude", []))
    xs = [ref] + years if ref else years
    f, ax = plt.subplots(figsize=(7.2, 3.4))
    for c, s in grp.items():
        idx = s / s.loc[base_y] * 100
        nc = sum(1 for u in main if u['cls'] == c and u['topic'] not in excl)
        ax.plot(xs, idx.reindex(xs), marker="o", lw=2.2, color=COL[c], label=f"{c.title()} (n={nc})")
        sub = [u["series"].value for u in main if u["cls"] == c and u["topic"] not in excl | sens]
        if sens and len(sub) < nc:
            s2 = pd.concat(sub, axis=1).sum(axis=1, min_count=1).reindex(xs)
            lab = ", ".join(classes.get(t, {}).get("label", t) for t in sens)
            ax.plot(xs, s2 / s2.loc[base_y] * 100, ls="--", lw=1.6, color=COL[c], alpha=.7, label=f"{c.title()} excl. {lab}")
    ax.axhline(100, color=COL["ref"], lw=1, ls=":")
    ax.axvspan(ref - .5, y0 - .5, color="#f5f5f4", zorder=0) if ref and y0 - ref > 1 else None
    ax.set_xticks(xs, [str(x) for x in xs])
    ax.set_ylabel(f"Notified cases, index {base_y} = 100"); ax.legend(frameon=False, fontsize=8, loc="upper left")
    ax.set_title(f"Viral vs bacterial notifications ({', '.join(classes.get(t,{}).get('label',t) for t in excl)} excluded)", loc="left", fontsize=10)
    chart_index = fig_b64(f)

    # ---- chart 2: small multiples incidence per 100k
    order = sorted(main, key=lambda u: (u["cls"] != "viral", u["label"]))
    n = len(order); ncol = 4; nrow = -(-n // ncol)
    f, axs = plt.subplots(nrow, ncol, figsize=(10, 2.1 * nrow), squeeze=False)
    for ax, u in zip(axs.flat, order):
        s = u["series"]; col = "inc100k" if s.inc100k.notna().any() else "value"
        ax.plot(years, s[col].reindex(years), marker="o", ms=3, lw=1.8, color=COL[u["cls"]])
        if ref in s.index:
            ax.axhline(s.loc[ref, col], color=COL["ref"], lw=1, ls=":")
        ax.set_title(u["label"], loc="left", fontsize=9, color=COL[u["cls"]], fontweight="bold")
        ax.set_xticks(years, [str(y)[2:] for y in years]); ax.set_ylim(bottom=0)
        ax.tick_params(labelsize=7)
        ax.text(.99, .04, "per 100k" if col == "inc100k" else "cases", transform=ax.transAxes, ha="right", fontsize=6.5, color="#6b7280")
    for ax in list(axs.flat)[n:]: ax.axis("off")
    f.tight_layout()
    chart_multi = fig_b64(f)

    # ---- chart 3: syndromic GP consultations
    chart_synd = ""
    if synd:
        f, ax = plt.subplots(figsize=(7.2, 2.8))
        for u, c in zip(synd, ["#6b7280", "#a16207", "#1d4ed8"]):
            s = u["series"].value.reindex(years)
            ax.plot(years, s / 1000, marker="o", lw=2, color=c, label=f"{u['label']} ({u['measure']})")
        ax.set_xticks(years); ax.set_ylabel("thousand (extrapolated)"); ax.legend(frameon=False, fontsize=8)
        chart_synd = fig_b64(f)

    # ---- table
    rows_html, tab = [], []
    for u in order:
        s = u["series"]
        v = {y: (s.value.get(y) if y in s.index else None) for y in [ref] + years}
        ch = pct(v[y0], v[y1]); vs_ref = pct(v[ref], v[y1])
        peak = int(s.value.reindex(years).idxmax())
        inc = s.inc100k.get(y1) if y1 in s.index else None
        trend = "rising" if ch is not None and ch > 15 else "falling" if ch is not None and ch < -15 else "stable"
        tab.append(dict(disease=u["label"], pathogen_class=u["cls"], system=u["system"], measure=u["measure"],
                        **{str(k): v[k] for k in v}, change_pct=ch, vs_ref_pct=vs_ref, inc100k_last=inc, peak_year=peak,
                        trend=trend, dataset_id=u["dataset_id"], source_file=u["source_file"]))
        cells = "".join(
            f'<td class="num" title="{html.escape(Path(u["source_file"]).parent.name)}/data.csv rows {u["rows"].get(y, "-")}">'
            f'{"–" if v[y] is None or pd.isna(v[y]) else f"{v[y]:,.0f}"}</td>' for y in [ref] + years)
        rows_html.append(
            f'<tr><td><span class="dot {u["cls"]}"></span>{html.escape(u["label"])}'
            f'{"<sup>*</sup>" if u["topic"] in excl else ""}</td><td>{u["cls"]}</td>{cells}'
            f'<td class="num {trend}">{fmt_pct(ch)}</td><td class="num">{fmt_pct(vs_ref)}</td>'
            f'<td class="num">{"–" if inc is None or pd.isna(inc) else f"{inc:.1f}"}</td><td>{peak}</td></tr>')
    pd.DataFrame(tab).to_csv(out / f"report_{cfg['id']}_table.csv", index=False)
    trace.to_csv(out / f"report_{cfg['id']}_trace.csv", index=False)

    # ---- headline numbers
    gv, gb = grp.get("viral"), grp.get("bacterial")
    tdf = pd.DataFrame(tab)
    risers = tdf.sort_values("change_pct", ascending=False).head(3)
    fallers = tdf.sort_values("change_pct").head(2)
    cards = [
        ("Viral (excl. COVID-19), vs " + str(ref), fmt_pct(pct(gv.get(ref), gv.get(y1))), f"{y0}→{y1}: {fmt_pct(pct(gv.get(y0), gv.get(y1)))} ({gv.get(y0):,.0f} → {gv.get(y1):,.0f})", "viral"),
        ("Bacterial, vs " + str(ref), fmt_pct(pct(gb.get(ref), gb.get(y1))), f"{y0}→{y1}: {fmt_pct(pct(gb.get(y0), gb.get(y1)))} ({gb.get(y0):,.0f} → {gb.get(y1):,.0f})", "bacterial"),
    ]
    cov = next((u for u in main if u["topic"] in excl), None)
    if cov is not None:
        cs = cov["series"].value
        cards.append(("COVID-19 notifications", fmt_pct(pct(cs.get(y0), cs.get(y1))), f"peak {int(cs.reindex(years).idxmax())}: {cs.max():,.0f}", "viral"))
    cards.append(("Strongest rise", risers.iloc[0].disease, f"{fmt_pct(risers.iloc[0].change_pct)} since {y0}", risers.iloc[0].pathogen_class))
    cards_html = "".join(f'<div class="card {c}"><div class="k">{html.escape(k)}</div><div class="v">{html.escape(str(v))}</div><div class="s">{html.escape(s)}</div></div>' for k, v, s, c in cards)

    bullets = [
        f"Bacterial notifications rose {fmt_pct(pct(gb.get(y0), gb.get(y1)))} between {y0} and {y1} and are {fmt_pct(pct(gb.get(ref), gb.get(y1)))} above {ref}. "
        f"Main contributors: {', '.join(tdf[tdf.pathogen_class=='bacterial'].sort_values('change_pct', ascending=False).disease.head(3))}.",
        f"Viral notifications excluding COVID-19 changed {fmt_pct(pct(gv.get(y0), gv.get(y1)))}, driven mainly by influenza, which was almost absent in {y0} "
        f"({tab[[t['disease'] for t in tab].index('Influenza')][str(y0)]:,.0f} cases) during pandemic measures." if "Influenza" in tdf.disease.values else
        f"Viral notifications excluding COVID-19 changed {fmt_pct(pct(gv.get(y0), gv.get(y1)))}.",
        *([f"Excluding influenza as well, viral notifications are {fmt_pct(pct(sum(u['series'].value.get(ref,0) for u in main if u['cls']=='viral' and u['topic'] not in excl|sens), sum(u['series'].value.get(y1,0) for u in main if u['cls']=='viral' and u['topic'] not in excl|sens)))} vs {ref}: the post-COVID viral rise is mostly an influenza rebound, while the bacterial rise is broad."] if (sens:=set(cfg.get("sensitivity_exclude", []))) else []),
        f"Largest relative increases {y0}→{y1}: " + "; ".join(f"{r.disease} {fmt_pct(r.change_pct)}" for r in risers.itertuples()) + ".",
        f"Largest decreases: " + "; ".join(f"{r.disease} {fmt_pct(r.change_pct)}" for r in fallers.itertuples()) + ".",
    ]

    skipped_html = "".join(f"<tr><td>{html.escape(t)}</td><td>{c}</td><td>{html.escape(r)}</td></tr>" for _, t, c, r in skipped)
    used_ids = {u["dataset_id"] for u in used}
    regv = reg[reg.status.str.startswith("ok")]
    src_html = "".join(
        f"<tr><td>{html.escape(str(r.topic))}</td><td>{html.escape(str(r.source_system))}</td><td>{r.publishing_date}</td>"
        f"<td>{'yes' if r.dataset_id in used_ids else 'no'}</td><td><code>{html.escape(str(Path(r.source_file).parent.name))}/data.csv</code></td>"
        f"<td><code>{r.sha256[:12]}</code></td><td class='num'>{int(r.rows):,}</td></tr>" for r in regv.itertuples())
    ndup = (reg.status == "duplicate_skipped").sum()
    qc = ""
    if len(checks):
        qs = checks[checks.dataset_id.isin(used_ids)]
        qc = (f"<p>{(qs.status=='PASS').sum()} checks passed, {(qs.status=='WARN').sum()} warnings, {(qs.status=='FAIL').sum()} failures "
              f"on the {len(used_ids)} datasets used.</p><table><tr><th>Dataset</th><th>Check</th><th>Status</th><th>Detail</th></tr>" +
              "".join(f"<tr><td>{html.escape(r.dataset_id.split('__')[0])}</td><td>{r.check}</td><td class='{r.status.lower()}'>{r.status}</td><td>{html.escape(str(r.detail))}</td></tr>"
                      for r in qs[qs.status != 'PASS'].itertuples()) + "</table>")
    pub = reg.publishing_date.dropna().max()

    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(cfg['title'])}</title>
<style>
:root{{--ink:#1c1917;--mute:#78716c;--line:#e7e5e4;--bg:#fafaf9;--viral:{COL['viral']};--bact:{COL['bacterial']}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 Georgia,'Times New Roman',serif}}
main{{max-width:1040px;margin:0 auto;padding:40px 28px 80px}}
h1{{font-size:34px;line-height:1.15;margin:.2em 0 .3em;font-weight:normal}}
h2{{font:600 13px/1.3 system-ui,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--mute);border-top:1px solid var(--line);padding-top:22px;margin-top:40px}}
.eyebrow{{font:600 12px system-ui,sans-serif;letter-spacing:.1em;text-transform:uppercase;color:var(--viral)}}
.lede{{font-size:18px;color:#44403c;max-width:760px}}
.meta{{font:12px system-ui,sans-serif;color:var(--mute)}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:26px 0}}
.card{{background:#fff;border:1px solid var(--line);border-top:4px solid var(--mute);padding:14px 16px;font-family:system-ui,sans-serif}}
.card.viral{{border-top-color:var(--viral)}} .card.bacterial{{border-top-color:var(--bact)}}
.card .k{{font-size:12px;color:var(--mute)}} .card .v{{font-size:26px;font-weight:600;margin:2px 0}} .card .s{{font-size:12px;color:#57534e}}
img{{max-width:100%;background:#fff;border:1px solid var(--line);padding:8px;box-sizing:border-box}}
table{{border-collapse:collapse;width:100%;font:12.5px system-ui,sans-serif;background:#fff}}
th,td{{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}} th{{background:#f5f5f4;font-weight:600}}
td.num{{text-align:right;font-variant-numeric:tabular-nums}} td[title]{{cursor:help}}
.rising{{color:#b91c1c;font-weight:600}} .falling{{color:#15803d;font-weight:600}}
.warn{{color:#a16207}} .fail{{color:#b91c1c;font-weight:600}}
.dot{{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;background:#999}} .dot.viral{{background:var(--viral)}} .dot.bacterial{{background:var(--bact)}}
ul.find li{{margin:.35em 0}} .note{{font:12.5px system-ui,sans-serif;color:var(--mute)}} code{{font-size:11px}}
</style></head><body><main>
<div class="eyebrow">Stakeholder report · {html.escape(cfg['id'].replace('_',' '))}</div>
<h1>{html.escape(cfg['title'])}, {y0}–{y1}</h1>
<p class="lede">{html.escape(cfg['question'])}</p>
<p class="meta">Source: FOPH Infectious Disease Dashboard (IDD) exports, published up to {pub}. National level (Switzerland + Liechtenstein), all ages, all sexes. Generated automatically by the harmonisation pipeline.</p>
<div class="cards">{cards_html}</div>
<h2>Key findings</h2><ul class="find">{''.join(f'<li>{html.escape(b)}</li>' for b in bullets)}</ul>
<h2>Viral vs bacterial, indexed to {base_y}</h2>
<img src="{chart_index}" alt="Index chart of viral and bacterial notifications">
<p class="note">Sum of notified cases per group, {base_y} (pre-COVID) = 100. 2020 is not shown. Dashed lines remove influenza, which collapsed in {y0} under pandemic measures and otherwise dominates the viral total. COVID-19 is excluded from the viral total because its volume (up to millions of cases) would hide every other trend; it is shown in the table and per-disease charts.</p>
<h2>Per disease: incidence per 100,000</h2>
<img src="{chart_multi}" alt="Small multiples per disease">
<p class="note">Dotted line = {ref} level. Orange = viral, teal = bacterial. Lyme borreliosis is a sentinel extrapolation, not a mandatory notification.</p>
<h2>Change table</h2>
<table><tr><th>Disease</th><th>Class</th><th>{ref}</th>{''.join(f'<th>{y}</th>' for y in years)}<th>{y0}→{y1}</th><th>vs {ref}</th><th>per 100k ({y1})</th><th>Peak</th></tr>{''.join(rows_html)}</table>
<p class="note">Hover any number to see the exact source file and row(s). <sup>*</sup> excluded from group totals. Rising/falling = change of more than ±15%.</p>
{f'<h2>Context: GP consultations for respiratory syndromes</h2><img src="{chart_synd}" alt="Syndromic consultations"><p class="note">Sentinella estimates; mixed viral and bacterial causes, so not assigned to either group.</p>' if chart_synd else ''}
<h2>Datasets not used in this report, and why</h2>
<table><tr><th>Topic</th><th>Class</th><th>Reason</th></tr>{skipped_html or '<tr><td colspan=3>None</td></tr>'}</table>
<h2>Data quality</h2>{qc}
<h2>Sources and traceability</h2>
<p class="note">{len(regv)} unique datasets harmonised ({ndup} duplicate downloads detected by file fingerprint and skipped). Every value in this report is listed with its source file and row in <code>report_{cfg['id']}_trace.csv</code>.</p>
<table><tr><th>Topic</th><th>System</th><th>Published</th><th>Used</th><th>File</th><th>SHA-256</th><th>Rows</th></tr>{src_html}</table>
</main></body></html>"""
    p = out / f"report_{cfg['id']}.html"
    p.write_text(page, encoding="utf-8")
    print(f"wrote {p}  ({len(used)} series used, {len(skipped)} skipped)")


if __name__ == "__main__":
    main()
