#!/usr/bin/env python3
"""
harmonise.py - turn every IDD dataset (data.csv + metadata.json) into ONE long table.

Data-agnostic: nothing here names a disease. Roles come from each dataset's metadata.json
(temporalVariables / groupingVariables / valueVariables), with value-pattern fallbacks.

Usage:  python harmonise.py <data_root> --out out/
Outputs:
  out/harmonised.parquet   one row per (dataset, measure, period, place, groups) value
  out/datasets.csv         one row per dataset: id, topic, source, hash, path, rows, status
  out/role_log.csv         how every column was classified, and why
"""
import argparse, hashlib, json, re, sys
from pathlib import Path
import pandas as pd

STAT_PATTERN = re.compile(r"(?:^min_|^median_|^max_|_mean$|_cumsum$|_\d+y$)")
KEEP_VALUE_COLS = ["value", "pop", "incValue", "prct"]   # kept if present
PLACE_RE = re.compile(r"^georegion\d*$")


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def find_datasets(root):
    """Any folder containing a data.csv and a JSON description file."""
    for csv in sorted(Path(root).rglob("data.csv")):
        jsons = [j for j in csv.parent.glob("*.json")]
        meta = next((j for j in jsons if "meta" in j.name.lower()), jsons[0] if jsons else None)
        yield csv, meta


def load_meta(path):
    if path is None or not path.exists():
        return {}
    txt = path.read_text(encoding="utf-8", errors="replace")
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        # repair truncated JSON by closing open brackets
        opens = []
        for ch in txt:
            if ch in "{[": opens.append(ch)
            elif ch in "}]" and opens: opens.pop()
        txt += "".join("}" if c == "{" else "]" for c in reversed(opens))
        try:
            return json.loads(txt)
        except Exception:
            return {}


def period_start(temporal, ttype):
    """Convert IDD period labels to a start date. Unknown -> NaT."""
    t = str(temporal)
    try:
        if re.fullmatch(r"\d{4}", t):
            return pd.Timestamp(int(t), 1, 1)
        m = re.fullmatch(r"(\d{4})-M(\d{2})", t)
        if m:
            return pd.Timestamp(int(m[1]), int(m[2]), 1)
        m = re.fullmatch(r"(\d{4})-W(\d{2})", t)
        if m:
            return pd.Timestamp.fromisocalendar(int(m[1]), int(m[2]), 1)
        return pd.Timestamp(t)
    except Exception:
        return pd.NaT


def classify_columns(df, meta):
    """Return {column: (role, reason)}."""
    roles = {}
    tv = meta.get("temporalVariables", {})
    gv = meta.get("groupingVariables", {})
    vv = meta.get("valueVariables", {})
    mv = meta.get("metaVariables", {})
    if tv.get("column"): roles[tv["column"]] = ("time", "metadata.temporalVariables")
    if tv.get("typeColumn"): roles[tv["typeColumn"]] = ("time_type", "metadata.temporalVariables")
    vc = mv.get("valueCategory", {}).get("column")
    if vc: roles[vc] = ("measure_name", "metadata.valueCategory")
    for name, g in gv.items():
        col = g.get("column", name)
        role = ("place" if PLACE_RE.match(col) else "age" if col.startswith("agegroup")
                else "sex" if col == "sex" else "breakdown")
        roles[col] = (role, "metadata.groupingVariables")
        if g.get("typeColumn"):
            roles[g["typeColumn"]] = (role + "_type", "metadata.groupingVariables")
    for col in vv:
        roles.setdefault(col, ("value" if col in KEEP_VALUE_COLS else "derived_value",
                               "metadata.valueVariables"))
    # fallbacks for columns the metadata did not describe
    for col in df.columns:
        if col in roles: continue
        s = df[col].dropna().astype(str)
        if col.endswith("_type"):
            roles[col] = ("type_column", "name pattern *_type")
        elif col in ("temporal", "date") or s.str.match(r"^\d{4}(-[MW]?\d{2})?").mean() > .9:
            roles[col] = ("time", "value pattern")
        elif pd.to_numeric(df[col], errors="coerce").notna().mean() > .9:
            roles[col] = ("derived_value", "numeric values, not in metadata")
        elif df[col].nunique() <= 60:
            roles[col] = ("annotation", "few distinct text values, not a metadata grouping")
        else:
            roles[col] = ("ignored", "high-cardinality text")
    return roles


def all_values(meta):
    """Values that mean 'total' for each grouping column."""
    out = {}
    for name, g in meta.get("groupingVariables", {}).items():
        col = g.get("column", name)
        vals = {"all"}
        if "allValue" in g: vals.add(str(g["allValue"]))
        for tv in (g.get("typeValues") or {}).values():
            if isinstance(tv, dict) and "allValue" in tv: vals.add(str(tv["allValue"]))
        out[col] = vals
    return out


def harmonise_one(csv, meta_path, ds_id):
    meta = load_meta(meta_path)
    mv = meta.get("metaVariables", {})
    df = pd.read_csv(csv, dtype=str, keep_default_na=False, na_values=["NA", ""])
    roles = classify_columns(df, meta)
    log = [dict(dataset_id=ds_id, column=c, role=r, reason=why) for c, (r, why) in roles.items()]

    by_role = lambda r: [c for c, (x, _) in roles.items() if x == r and c in df.columns]
    time_c = (by_role("time") or [None])[0]
    ttype_c = (by_role("time_type") or [None])[0]
    meas_c = (by_role("measure_name") or [None])[0]
    place_c = by_role("place"); place_t = by_role("place_type")
    age_c = (by_role("age") or [None])[0]
    sex_c = (by_role("sex") or [None])[0]
    brk_c = by_role("breakdown")
    if time_c is None:
        raise ValueError("no time column found")

    alls = all_values(meta)
    # a grouping column with a single distinct value is not a real split -> treat as total
    for c in list(alls) + brk_c:
        if c in df.columns and df[c].nunique(dropna=True) <= 1:
            alls.setdefault(c, {"all"}).update(df[c].dropna().astype(str).unique())
    out = pd.DataFrame({
        "dataset_id": ds_id,
        "topic": mv.get("topic", csv.parent.name),
        "source_system": mv.get("source", "unknown"),
        "measure": df[meas_c] if meas_c else "value",
        "period": df[time_c],
        "period_type": df[ttype_c] if ttype_c else "unknown",
        "place": df[place_c[-1]] if place_c else "all",
        "place_type": df[place_t[-1]] if place_t else "unknown",
        "age_group": df[age_c] if age_c else "all",
        "sex": df[sex_c] if sex_c else "all",
    })
    if brk_c:
        out["breakdown"] = df[brk_c].astype(str).apply(
            lambda r: ";".join(f"{k}={v}" for k, v in r.items() if v not in alls.get(k, {"all"})), axis=1)
    else:
        out["breakdown"] = ""
    for c in KEEP_VALUE_COLS:
        out[c] = pd.to_numeric(df[c], errors="coerce") if c in df.columns else pd.NA
    # total flag: every grouping column at its 'all' value (place totals = national-level types)
    grp_cols = [c for c in alls if c in df.columns and not PLACE_RE.match(c)]
    is_tot = pd.Series(True, index=df.index)
    for c in grp_cols:
        is_tot &= df[c].isin(alls[c])
    out["is_total"] = is_tot
    out["is_stat_row"] = out["measure"].astype(str).str.contains(STAT_PATTERN)
    uniq = out["period"].drop_duplicates()
    starts = {p: period_start(p, None) for p in uniq}
    out["period_start"] = out["period"].map(starts)
    out["year"] = out["period_start"].dt.year
    out["source_file"] = str(csv)
    out["source_row"] = df.index + 2          # +2 = header line + 1-based
    return out, log, meta, len(df)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--out", default="out")
    a = ap.parse_args(argv)
    outdir = Path(a.out); outdir.mkdir(parents=True, exist_ok=True)

    frames, logs, registry, seen = [], [], [], {}
    for csv, meta in find_datasets(a.root):
        h = sha256(csv)
        rec = dict(source_file=str(csv), metadata_file=str(meta) if meta else "", sha256=h)
        if h in seen:
            registry.append({**rec, "dataset_id": seen[h], "status": "duplicate_skipped"}); continue
        try:
            m = load_meta(meta)
            mv = m.get("metaVariables", {})
            ds_id = f"{mv.get('topic', csv.parent.name)}__{mv.get('source', 'unknown')}__{h[:8]}"
            df, log, m, n = harmonise_one(csv, meta, ds_id)
            seen[h] = ds_id
            frames.append(df); logs += log
            registry.append({**rec, "dataset_id": ds_id, "topic": mv.get("topic"),
                             "source_system": mv.get("source"), "publishing_date": mv.get("publishingDate"),
                             "rows": n, "status": "ok" if m else "ok_no_metadata"})
            print(f"  ok   {ds_id}  ({n:,} rows)")
        except Exception as e:
            registry.append({**rec, "dataset_id": "", "status": f"error: {e}"})
            print(f"  FAIL {csv}: {e}", file=sys.stderr)

    if not frames:
        sys.exit("no datasets harmonised")
    allh = pd.concat(frames, ignore_index=True)
    for c in ["value", "pop", "incValue", "prct"]:
        allh[c] = pd.to_numeric(allh[c], errors="coerce")
    allh.to_parquet(outdir / "harmonised.parquet", index=False)
    pd.DataFrame(registry).to_csv(outdir / "datasets.csv", index=False)
    pd.DataFrame(logs).to_csv(outdir / "role_log.csv", index=False)
    print(f"harmonised {allh.dataset_id.nunique()} datasets, {len(allh):,} rows -> {outdir}")


if __name__ == "__main__":
    main()
