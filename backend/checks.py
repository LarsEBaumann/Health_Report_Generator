#!/usr/bin/env python3
"""Validate harmonised data. A failed gate always exits nonzero."""
import argparse
import json
from pathlib import Path
import pandas as pd
from common import digest, write_json

KEY = ['dataset_id', 'measure', 'period', 'period_type', 'groups_json']
COUNT_MEASURES = {'cases', 'consultations'}


def canonical_metadata(out, row):
    path = Path(out) / 'snapshots' / str(row.snapshot_id) / str(row.metadata_file)
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError, TypeError):
        return f"unreadable:{row.metadata_sha256}"
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)



def run(d):
    res = []
    def add(ds, check, status, detail):
        res.append(dict(dataset_id=ds, check=check, status=status, detail=detail))
    for ds, g in d.groupby('dataset_id'):
        for check, n in [('no_duplicate_rows', int(g.duplicated(KEY).sum())),
                         ('periods_parseable', int(g.period_start.isna().sum())),
                         ('values_numeric', int(g.invalid_value.sum())),
                         ('finite_values', int(g.value.isin([float('inf'),float('-inf')]).sum())),
                         ('no_negative_counts', int(((g.value < 0) & g.measure.isin(COUNT_MEASURES)).sum()))]:
            add(ds, check, 'FAIL' if n else 'PASS', str(n))
        missing = g.value.isna().mean()
        add(ds, 'value_present', 'WARN' if missing >= .5 else 'PASS', f'{missing:.1%} missing; report selection requires complete values')
        # Only additive counts and explicit national totals can be reconciled.
        b = g[g.is_total & ~g.is_stat_row & g.measure.isin(COUNT_MEASURES) & g.place_type.isin(['CHFL','country'])]
        compared = 0
        for (measure, place, place_type, year), q in b.groupby(['measure','place','place_type','year']):
            y, m = q[q.period_type == 'year'], q[q.period_type == 'month']
            if len(y) != 1 or len(m) != 12 or m.period_start.dt.month.nunique() != 12 or m.value.isna().any() or y.value.isna().any():
                continue
            compared += 1
            delta = abs(y.value.iloc[0] - m.value.sum()) / max(abs(y.value.iloc[0]), 1)
            add(ds, 'year_equals_sum_of_months', 'FAIL' if delta > .02 else 'PASS', f'{measure}/{place}/{int(year)}: difference {delta:.2%}; tolerance 2%')
        if not compared:
            add(ds, 'year_equals_sum_of_months', 'SKIP', 'No complete compatible annual/monthly pair')
        # Do not compare Swiss cantons to CH+FL or an incomplete set of cantons.
        cantons = set('ZH BE LU UR SZ OW NW GL ZG FR SO BS BL SH AR AI SG GR AG TG TI VD VS NE GE JU'.split())
        compared = 0
        b = g[g.is_total & ~g.is_stat_row & g.measure.isin(COUNT_MEASURES) & (g.period_type == 'year')]
        for (measure, year), q in b.groupby(['measure','year']):
            c = q[q.place_type == 'canton']; n = q[(q.place == 'CH') & (q.place_type == 'country')]
            if len(n) != 1 or len(c) != 26 or set(c.place.str.upper()) != cantons or c.value.isna().any() or n.value.isna().any():
                continue
            compared += 1
            delta = abs(c.value.sum() - n.value.iloc[0]) / max(abs(n.value.iloc[0]), 1)
            add(ds, 'cantons_sum_to_national', 'FAIL' if delta > .05 else 'PASS', f'{measure}/{int(year)}: difference {delta:.2%}; tolerance 5%')
        if not compared:
            add(ds, 'cantons_sum_to_national', 'SKIP', 'Requires 26 distinct Swiss cantons and a CH national total')
    return pd.DataFrame(res)


def validate(out):
    out = Path(out); marker = out / 'validated.json'
    marker.unlink(missing_ok=True)
    d = pd.read_parquet(out / 'harmonised.parquet')
    reg = pd.read_csv(out / 'datasets.csv').fillna('')
    r = run(d)
    extra = []
    for x in reg[reg.status == 'quarantined'].itertuples():
        extra.append(dict(dataset_id=x.source_file, check='metadata_schema', status='FAIL', detail=x.detail))
    for h, g in reg.groupby('sha256'):
        if g.metadata_sha256.nunique() > 1:
            semantic_metadata = {canonical_metadata(out, row) for row in g.itertuples()}
            if len(semantic_metadata) > 1:
                extra.append(dict(dataset_id=h, check='metadata_conflict', status='FAIL', detail='Identical data bytes have different metadata; resolve explicitly'))
    r = pd.concat([r, pd.DataFrame(extra)], ignore_index=True)
    r.to_csv(out / 'checks.csv', index=False)
    if (r.status == 'FAIL').any():
        raise ValueError(f"{(r.status == 'FAIL').sum()} blocking checks failed; inspect {out / 'checks.csv'}")
    write_json(marker, {'schema_version': '2.0', 'files': {n: digest(out / n) for n in ['harmonised.parquet','datasets.csv','checks.csv','harmonised_snapshot.json']}})
    return r

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--out', default='out'); a = ap.parse_args()
    try:
        print(validate(a.out).status.value_counts().to_string())
    except ValueError as e:
        ap.exit(1, str(e) + '\n')
