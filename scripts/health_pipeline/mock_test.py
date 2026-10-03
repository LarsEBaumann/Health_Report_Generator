#!/usr/bin/env python3
"""
mock_test.py - automated mock test of the whole workflow.

Usage: python mock_test.py <data_root> [--fast]
Runs: full run + timing, repeatability, traceability, robustness (deliberately broken inputs),
data checks and stakeholder coverage. Writes mock_test/mock_test_report.html and prints PASS/FAIL.
--fast skips data files >5 MB in the robustness tests.
"""
import argparse, json, random, shutil, subprocess, sys, time, hashlib, html
from pathlib import Path
import pandas as pd

HERE = Path(__file__).parent
PY = sys.executable
results = []


def rec(test, ok, detail):
    results.append(dict(test=test, status="PASS" if ok else "FAIL", detail=detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {test}: {detail}")


def pipeline(root, out):
    out.mkdir(parents=True, exist_ok=True)
    steps = [[PY, HERE / "harmonise.py", root, "--out", out],
             [PY, HERE / "checks.py", "--out", out]]
    for sh in sorted((HERE / "config/stakeholders").glob("*.json")):
        steps.append([PY, HERE / "report.py", "--stakeholder", sh, "--out", out])
    log = ""
    for s in steps:
        p = subprocess.run([str(x) for x in s], capture_output=True, text=True)
        log += p.stdout + p.stderr
        if p.returncode != 0:
            return False, log
    return True, log


def table_hash(out):
    d = pd.read_parquet(out / "harmonised.parquet").drop(columns=["source_file"])
    return hashlib.sha256(pd.util.hash_pandas_object(d, index=False).values.tobytes()).hexdigest()


def copy_subset(src, dst, fast):
    for csv in Path(src).rglob("data.csv"):
        if fast and csv.stat().st_size > 5e6: continue
        t = dst / csv.parent.relative_to(src); t.mkdir(parents=True, exist_ok=True)
        for f in csv.parent.iterdir():
            if f.is_file(): shutil.copy(f, t / f.name)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("root"); ap.add_argument("--fast", action="store_true")
    ap.add_argument("--work", default="mock_test")
    a = ap.parse_args()
    work = Path(a.work); shutil.rmtree(work, ignore_errors=True); work.mkdir()
    stakeholders = [json.loads(p.read_text()) for p in sorted((HERE / "config/stakeholders").glob("*.json"))]

    # 1. full run + timing
    t = time.time(); ok, log = pipeline(a.root, work / "run1"); dt = time.time() - t
    rec("full_run", ok, f"{dt:.0f}s" + ("" if ok else " | " + log[-300:]))
    if not ok: return finish(work)
    reg = pd.read_csv(work / "run1/datasets.csv")
    rec("all_datasets_harmonised", not reg.status.str.startswith("error").any(),
        f"{(reg.status=='ok').sum()} ok, {(reg.status=='duplicate_skipped').sum()} duplicates skipped, "
        f"{reg.status.str.startswith('error').sum()} errors")
    for sh in stakeholders:
        rec(f"report_created[{sh['id']}]", (work / f"run1/report_{sh['id']}.html").exists(), "html written")

    # 2. repeatability
    ok2, _ = pipeline(a.root, work / "run2")
    same = ok2 and table_hash(work / "run1") == table_hash(work / "run2")
    tabs = all(pd.read_csv(work / f"run1/report_{s['id']}_table.csv").equals(pd.read_csv(work / f"run2/report_{s['id']}_table.csv")) for s in stakeholders)
    rec("repeatable_harmonised_table", same, "identical hash on two runs")
    rec("repeatable_report_numbers", tabs, "report tables identical on two runs")

    # 3. traceability: random report numbers -> raw file + row
    for sh in stakeholders:
        tr = pd.read_csv(work / f"run1/report_{sh['id']}_trace.csv")
        sample = tr.sample(min(10, len(tr)), random_state=1)
        good = 0
        for r in sample.itertuples():
            raw = pd.read_csv(r.source_file, dtype=str, keep_default_na=False)
            v = pd.to_numeric(raw.iloc[r.source_row - 2]["value"], errors="coerce")
            good += abs(v - r.value) < 1e-6
        rec(f"traceability[{sh['id']}]", good == len(sample), f"{good}/{len(sample)} sampled numbers match the raw row")
        tab = pd.read_csv(work / f"run1/report_{sh['id']}_table.csv")
        y = str(sh["years"][1])
        sums = tr[tr.year == int(y)].groupby("dataset_id").value.sum()
        sums = sums[sums.index.isin(tab.dataset_id)]
        m = tab.set_index("dataset_id")[y].reindex(sums.index)
        rec(f"table_equals_trace_sum[{sh['id']}]", bool(((m - sums).abs() < 1e-6).all()), f"{len(sums)} diseases, year {y}")

    # 4. robustness: deliberately broken inputs
    base = work / "broken_base"; copy_subset(a.root, base, a.fast)
    dirs = sorted({p.parent for p in base.rglob("data.csv")})
    random.seed(7)
    cases = {}
    def mk(name, fn):
        d = work / f"broken_{name}"; shutil.copytree(base, d); fn(d); cases[name] = d
    def drop_col(d):
        f = next(d.rglob("data.csv")); df = pd.read_csv(f, dtype=str); df.drop(columns=[c for c in df.columns if c.startswith("agegroup")]).to_csv(f, index=False)
    def rename_folder(d):
        p = sorted(d.rglob("data.csv"))[1].parent; p.rename(p.with_name("zz renamed (copy) 2"))
    def no_meta(d):
        for j in sorted(d.rglob("data.csv"))[2].parent.glob("*.json"): j.unlink()
    def empty_file(d):
        e = d / "EMPTY_dataset"; e.mkdir(); (e / "data.csv").write_text(""); (e / "metadata.json").write_text("{}")
    def truncated_meta(d):
        j = next(sorted(d.rglob("data.csv"))[3].parent.glob("*.json")); j.write_text(j.read_text()[:len(j.read_text()) // 2])
    def messy_new(d):
        m = d / "NEW_disease_x"; m.mkdir()
        pd.DataFrame({"valueCategory": "cases", "temporal": [f"{y}" for y in range(2018, 2026)], "temporal_type": "year",
                      "georegion": "CHFL", "georegion_type": "CHFL", "serotype": "all", "value": [5, 7, "NA", 9, 3, 8, 12, 4]}
                     ).to_csv(m / "data.csv", index=False)
        (m / "metadata.json").write_text(json.dumps({"metaVariables": {"topic": "mystery_fever", "source": "test"}}))
    for n, fn in [("drop_age_column", drop_col), ("renamed_folder", rename_folder), ("missing_metadata", no_meta),
                  ("empty_dataset", empty_file), ("truncated_metadata", truncated_meta), ("unknown_new_disease", messy_new)]:
        try:
            mk(n, fn)
        except Exception as e:
            rec(f"robustness[{n}]", False, f"could not build case: {e}"); continue
        ok, log = pipeline(cases[n], cases[n] / "out")
        reg = pd.read_csv(cases[n] / "out/datasets.csv") if (cases[n] / "out/datasets.csv").exists() else pd.DataFrame()
        errs = reg[reg.status.astype(str).str.startswith("error")] if len(reg) else reg
        rec(f"robustness[{n}]", ok, "pipeline finished" + (f"; logged {len(errs)} skipped dataset(s): {errs.status.iloc[0][:80]}" if len(errs) else "") + ("" if ok else " | " + log[-200:]))

    # 5. data checks
    ch = pd.read_csv(work / "run1/checks.csv")
    rec("data_checks_no_fail", (ch.status == "FAIL").sum() == 0,
        f"{(ch.status=='PASS').sum()} pass, {(ch.status=='WARN').sum()} warn, {(ch.status=='FAIL').sum()} fail")

    # 6. stakeholder coverage
    for sh in stakeholders:
        h = (work / f"run1/report_{sh['id']}.html").read_text()
        need = ["Key findings", "Change table", "Datasets not used", "Sources and traceability", "Data quality"]
        miss = [n for n in need if n not in h]
        rec(f"report_sections[{sh['id']}]", not miss, "all sections present" if not miss else f"missing {miss}")
        tab = pd.read_csv(work / f"run1/report_{sh['id']}_table.csv")
        cls = set(tab.pathogen_class)
        rec(f"compares_required_groups[{sh['id']}]", set(sh["classes_in_main_comparison"]) <= cls, f"groups present: {sorted(cls)}")
    finish(work)


def finish(work):
    df = pd.DataFrame(results); df.to_csv(work / "mock_test_results.csv", index=False)
    n_ok = (df.status == "PASS").sum()
    rows = "".join(f"<tr><td>{html.escape(r.test)}</td><td style='color:{'#15803d' if r.status=='PASS' else '#b91c1c'};font-weight:600'>{r.status}</td><td>{html.escape(str(r.detail))}</td></tr>" for r in df.itertuples())
    (work / "mock_test_report.html").write_text(
        f"<!doctype html><meta charset=utf-8><title>Mock test</title><body style='font:14px system-ui;max-width:1000px;margin:30px auto'>"
        f"<h1>Mock test: {n_ok}/{len(df)} passed</h1><p>Not automated: the human check that a stakeholder can answer their question in 2 minutes.</p>"
        f"<table border=1 cellpadding=6 style='border-collapse:collapse;width:100%'><tr><th>Test</th><th>Status</th><th>Detail</th></tr>{rows}</table>")
    print(f"\n{n_ok}/{len(df)} tests passed -> {work/'mock_test_report.html'}")
    sys.exit(0 if n_ok == len(df) else 1)


if __name__ == "__main__":
    main()
