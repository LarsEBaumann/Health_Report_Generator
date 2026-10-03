#!/usr/bin/env python3
"""
checks.py - automatic quality checks on the harmonised table. No disease names in code.

Usage: python checks.py --out out/
Writes out/checks.csv  (dataset_id, check, status PASS/WARN/FAIL, detail)
"""
import argparse
from pathlib import Path
import pandas as pd

KEY = ["dataset_id", "measure", "period", "period_type", "place", "place_type",
       "age_group", "sex", "breakdown"]


def run(d):
    res = []
    add = lambda ds, chk, ok, detail, warn=False: res.append(
        dict(dataset_id=ds, check=chk, status="PASS" if ok else ("WARN" if warn else "FAIL"), detail=detail))
    for ds, g in d.groupby("dataset_id"):
        dup = g.duplicated(KEY).sum()
        add(ds, "no_duplicate_rows", dup == 0, f"{dup} duplicated keys", warn=True)
        neg = (g["value"] < 0).sum()
        add(ds, "no_negative_values", neg == 0, f"{neg} negative values")
        bad = g["period_start"].isna().sum()
        add(ds, "periods_parseable", bad == 0, f"{bad} unparseable periods")
        miss = g["value"].isna().mean() if g["value"].notna().any() else 1.0
        add(ds, "value_present", miss < .5, f"{miss:.0%} of values missing", warn=True)

        # internal consistency: yearly national total == sum of monthly national totals
        base = g[g.is_total & ~g.is_stat_row & g.value.notna()]
        nat = base[base.place_type.isin(["CHFL", "country"]) & base.place.isin(["CHFL", "CH"])]
        yr = nat[nat.period_type == "year"].groupby(["measure", "place", "year"]).value.sum()
        mo = nat[nat.period_type == "month"].groupby(["measure", "place", "year"]).value.sum()
        both = pd.concat([yr.rename("y"), mo.rename("m")], axis=1).dropna()
        if len(both):
            rel = ((both.y - both.m).abs() / both.y.clip(lower=1))
            badn = int((rel > .02).sum())
            add(ds, "year_equals_sum_of_months", badn == 0,
                f"{badn}/{len(both)} years differ >2% (max {rel.max():.1%})", warn=True)
        # canton sum == national (yearly)
        ct = base[(base.place_type == "canton") & (base.period_type == "year")]
        if len(ct) and len(yr):
            cs = ct.groupby(["measure", "year"]).value.sum()
            ny = yr.groupby(level=["measure", "year"]).max()
            j = pd.concat([cs.rename("c"), ny.rename("n")], axis=1).dropna()
            if len(j):
                rel = ((j.c - j.n).abs() / j.n.clip(lower=1))
                badn = int((rel > .05).sum())
                add(ds, "cantons_sum_to_national", badn == 0,
                    f"{badn}/{len(j)} years differ >5% (max {rel.max():.1%})", warn=True)
    return pd.DataFrame(res)


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="out")
    a = ap.parse_args(argv)
    d = pd.read_parquet(Path(a.out) / "harmonised.parquet")
    r = run(d)
    r.to_csv(Path(a.out) / "checks.csv", index=False)
    print(r.status.value_counts().to_string())
    for _, x in r[r.status != "PASS"].iterrows():
        print(f"  {x.status:4} {x.dataset_id:70} {x.check}: {x.detail}")


if __name__ == "__main__":
    main()
