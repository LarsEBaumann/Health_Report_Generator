"""Validated requests and independent dataset trends; legacy comparisons stay separate."""
import argparse
import importlib.metadata
import json
import platform
import re
import shutil
import subprocess
import tempfile
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from jsonschema import Draft202012Validator
from common import digest, object_hash, write_json
from inventory import verify
from checks import run as run_checks

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BUNDLE_FILES = ['request.json', 'resolved_settings.json', 'snapshot.json', 'catalogue.csv',
                'series.csv', 'coverage.csv', 'selection.csv', 'sources.csv', 'lineage.csv', 'checks.csv']
PREP_FILES = ['harmonised.parquet', 'datasets.csv', 'role_log.csv', 'harmonised_snapshot.json']


def read_request(path):
    def unique(pairs):
        d = {}
        for key, value in pairs:
            if key in d:
                raise ValueError(f'Duplicate JSON field: {key}')
            d[key] = value
        return d
    request = json.loads(Path(path).read_text(), object_pairs_hook=unique)
    schema = json.loads((REPO / 'workflow/request.schema.json').read_text())
    errors = sorted(Draft202012Validator(schema).iter_errors(request), key=lambda e: str(e.path))
    if errors:
        raise ValueError('Invalid request: ' + '; '.join(e.message for e in errors))
    return request


def preparation_key(snapshot_id):
    names = ['scripts/health_pipeline/' + n for n in ['harmonise.py', 'inventory.py', 'common.py', 'request_pipeline.py', 'requirements.lock.txt']]
    return object_hash({'snapshot_id': snapshot_id,
                        'code_and_environment': {n: digest(REPO / n) for n in names},
                        'runtime': {'python': platform.python_version(), **{n: importlib.metadata.version(n) for n in ['pandas', 'pyarrow']}}})


def seal_prepared(out):
    out = Path(out)
    write_json(out / 'prepared.json', {'files': {n: digest(out / n) for n in PREP_FILES}})


def verify_prepared(out):
    out = Path(out)
    marker = json.loads((out / 'prepared.json').read_text())
    if set(marker['files']) != set(PREP_FILES):
        raise ValueError('Invalid prepared cache manifest')
    for n, h in marker['files'].items():
        if digest(out / n) != h:
            raise ValueError(f'Prepared cache integrity failure: {n}; remove this cache entry and rerun')


def catalogue(reg):
    """Folder IDs are public IDs; exact duplicate exports remain selectable aliases."""
    rows = []
    for r in reg.to_dict('records'):
        folder = Path(r['source_file']).parent.name
        public_id = re.sub(r' \(\d+\)$', '', folder)
        rows.append({'dataset': public_id, 'dataset_id': r.get('dataset_id', ''),
                     'source_file': r['source_file'], 'sha256': r.get('sha256', ''),
                     'metadata_sha256': r.get('metadata_sha256', ''), 'status': r['status'],
                     'detail': r.get('detail', '')})
    return pd.DataFrame(rows)


def select_dataset(d, name):
    # v1 supports explicit national count totals only. New source types need adapters.
    q = d[d.is_total & ~d.is_stat_row].copy()
    geo = next((x for x in ['CHFL', 'CH'] if (q.place == x).any()), None)
    if geo is None:
        raise ValueError(f'{name}: no explicit national total; a dataset adapter is required (no totals inferred)')
    q = q[q.place == geo]
    measure = next((x for x in ['cases', 'consultations'] if (q.measure == x).any()), None)
    if measure is None:
        raise ValueError(f'{name}: unsupported measure; v1 supports cases or consultations, not wastewater, positivity or sequencing')
    q = q[q.measure == measure]
    # Select a published frequency; never add weekly/monthly/annual rows together.
    kinds = ['day', 'week', 'iso_week', 'month', 'year']
    period_type = next((x for x in kinds if (q.period_type == x).any()), None)
    if period_type is None:
        raise ValueError(f'{name}: unsupported time frequency {sorted(q.period_type.unique())}')
    q = q[q.period_type == period_type].sort_values('period_start')
    if q.period_start.duplicated().any():
        raise ValueError(f'{name}: ambiguous multiple totals per period; a dataset adapter is required')
    if q.value.notna().sum() == 0:
        raise ValueError(f'{name}: selected series has no observed values')
    return q, {'dataset': name, 'geography': geo, 'measure': measure, 'period_type': period_type,
               'filters': 'is_total=true; is_stat_row=false', 'aggregation': 'none',
               'frequency_policy': 'finest supported published frequency', 'time_range': 'all available periods'}


def analyse_request(prepared, request_path, snapshot_path, dest):
    prepared, dest = Path(prepared), Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / 'bundle.json').unlink(missing_ok=True)
    request = read_request(request_path)
    archive_root, snapshot = verify(snapshot_path)
    verify_prepared(prepared)
    if json.loads((prepared / 'harmonised_snapshot.json').read_text())['snapshot_id'] != snapshot['snapshot_id']:
        raise ValueError('Prepared data and requested snapshot differ')
    reg = pd.read_csv(prepared / 'datasets.csv').fillna('')
    cat = catalogue(reg)
    cat.to_csv(dest / 'catalogue.csv', index=False)
    frame = pd.read_parquet(prepared / 'harmonised.parquet')
    resolved, all_series, all_checks, coverage, source_rows = [], [], [], [], []
    seen = set()
    for name in request['datasets']:
        candidates = cat[cat.dataset == name]
        if candidates.empty:
            raise ValueError(f'Unknown dataset: {name}; inspect catalogue.csv')
        if (candidates.status == 'quarantined').any():
            raise ValueError(f'{name}: quarantined input: ' + '; '.join(candidates.detail))
        ids = candidates.dataset_id.unique()
        if len(ids) != 1:
            raise ValueError(f'{name}: ambiguous folder identifier; multiple distinct datasets')
        ds = ids[0]
        if ds in seen:
            raise ValueError(f'{name}: duplicates an already selected export; select it only once')
        seen.add(ds)
        source = reg[(reg.dataset_id == ds) & (reg.status == 'ok')]
        if len(source) != 1:
            raise ValueError(f'{name}: canonical source missing or ambiguous')
        src = source.iloc[0].to_dict()
        if reg[reg.sha256 == src['sha256']].metadata_sha256.nunique() > 1:
            raise ValueError(f'{name}: conflicting metadata for identical data')
        g = frame[frame.dataset_id == ds]
        checks = run_checks(g)
        all_checks.append(checks.assign(dataset=name))
        pd.concat(all_checks).to_csv(dest / 'checks.csv', index=False)
        if (checks.status == 'FAIL').any():
            raise ValueError(f'{name}: blocking data checks failed; inspect checks.csv')
        q, settings = select_dataset(g, name)
        settings['dataset_id'] = ds
        settings['source_system'] = src['source_system']
        settings['label'] = src['topic'].replace('_', ' ').title() + ' — ' + {'mandatory_reporting_system': 'Mandatory surveillance', 'sentinella_reporting_system': 'Sentinella'}.get(src['source_system'], src['source_system'])
        metadata = json.loads((archive_root / src['metadata_file']).read_text())
        settings['value_description'] = metadata['valueVariables'].get('value', {}).get('description', '')
        settings['unit'] = ('Estimated cases' if src['source_system'] == 'sentinella_reporting_system' and settings['measure'] == 'cases'
                            else 'Estimated consultations' if src['source_system'] == 'sentinella_reporting_system'
                            else 'Reported cases' if settings['measure'] == 'cases' else 'Reported consultations')
        resolved.append(settings)
        q = q.copy()
        q['observed_row'] = True
        freq = {'day': 'D', 'week': '7D', 'iso_week': '7D', 'month': 'MS', 'year': 'YS'}[settings['period_type']]
        expected = pd.date_range(q.period_start.min(), q.period_start.max(), freq=freq)
        if not q.period_start.isin(expected).all():
            raise ValueError(f'{name}: period dates do not align with the declared frequency')
        q = q.set_index('period_start').reindex(expected).rename_axis('date').reset_index()
        q['dataset'] = name
        q['unit'] = settings['unit']
        q['geography'] = settings['geography']
        q['observation_status'] = ['missing_period' if pd.isna(x) else 'missing_value' if pd.isna(v) else 'observed'
                                   for x, v in zip(q.observed_row, q.value)]
        q['completeness'] = q.data_complete.map({True: 'complete', False: 'incomplete'}).fillna('unknown')
        q['metric_id'] = [f'{name}:{x:%Y-%m-%d}:{settings["measure"]}' for x in q.date]
        q['source_sha256'] = q.source_file.map(lambda x: src['sha256'] if pd.notna(x) else None)
        columns = ['metric_id', 'dataset', 'date', 'period', 'value', 'unit', 'geography', 'observation_status',
                   'completeness', 'source_file', 'source_row', 'source_sha256']
        all_series.append(q[columns])
        coverage.append({'dataset': name, 'first_period': str(q.date.min().date()), 'last_period': str(q.date.max().date()),
                         'expected_periods': len(q), 'observed_values': int(q.value.notna().sum()),
                         'missing_periods': int((q.observation_status == 'missing_period').sum()),
                         'missing_values': int((q.observation_status == 'missing_value').sum()),
                         'incomplete_periods': int((q.completeness == 'incomplete').sum()),
                         'unknown_completeness': int((q.completeness == 'unknown').sum())})
        source_rows.append({'dataset': name, **src})
    series = pd.concat(all_series, ignore_index=True)
    series.to_csv(dest / 'series.csv', index=False, date_format='%Y-%m-%d')
    links = series[series.source_row.notna()][['metric_id', 'source_file', 'source_row', 'source_sha256']].copy()
    links['source_column'] = 'value'; links['transformation'] = 'published_value (no aggregation)'
    links.to_csv(dest / 'lineage.csv', index=False)
    pd.DataFrame(coverage).to_csv(dest / 'coverage.csv', index=False)
    pd.DataFrame(resolved).to_csv(dest / 'selection.csv', index=False)
    pd.DataFrame(source_rows).to_csv(dest / 'sources.csv', index=False)
    write_json(dest / 'request.json', request)
    write_json(dest / 'snapshot.json', snapshot)
    write_json(dest / 'resolved_settings.json', {'schema_version': '1.0', 'audience': request['audience'],
                                               'analysis': 'independent_dataset_trends', 'datasets': resolved})
    write_json(dest / 'bundle.json', {'schema_version': '1.0', 'request_hash': object_hash(request),
                                     'snapshot_id': snapshot['snapshot_id'],
                                     'files': {n: digest(dest / n) for n in BUNDLE_FILES}})


def render(bundle, fmt, output, quarto='quarto'):
    bundle, output = Path(bundle), Path(output)
    manifest = json.loads((bundle / 'bundle.json').read_text())
    for n in BUNDLE_FILES:
        if digest(bundle / n) != manifest['files'][n]:
            raise ValueError(f'Bundle integrity failure: {n}')
    request = read_request(bundle / 'request.json')
    if fmt not in request['formats']:
        raise ValueError(f'Format {fmt} was not requested')
    try:
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        commit = 'unavailable'
    provenance = {'schema_version': '1.0', 'request': request, 'snapshot_id': manifest['snapshot_id'],
                  'filters': json.loads((bundle / 'resolved_settings.json').read_text()),
                  'sources': pd.read_csv(bundle / 'sources.csv').fillna('').to_dict('records'),
                  'rendered_at': datetime.now(timezone.utc).isoformat(), 'git_commit': commit,
                  'software': {'python': platform.python_version(), 'pandas': pd.__version__,
                               'quarto': subprocess.check_output([quarto, '--version'], text=True).strip(),
                               'r': subprocess.check_output(['Rscript', '-e', 'cat(R.version.string)'], text=True).strip()},
                  'code_sha256': {str(p.relative_to(REPO)): digest(p) for p in
                                  [HERE / n for n in ['request_pipeline.py', 'harmonise.py', 'checks.py', 'inventory.py', 'common.py', 'templates/request_report.qmd', 'requirements.lock.txt']]
                                  + [REPO / n for n in ['renv.lock', 'Snakefile', 'workflow/request.smk', 'workflow/request.schema.json']]},
                  'bundle_sha256': digest(bundle / 'bundle.json')}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for n in BUNDLE_FILES:
            shutil.copyfile(bundle / n, tmp / n)
        shutil.copyfile(HERE / 'templates/request_report.qmd', tmp / 'report.qmd')
        write_json(tmp / 'provenance.json', provenance)
        # HTML has a machine-readable embedded record; PDF has a JSON text appendix.
        record = json.dumps(provenance, ensure_ascii=True).replace('<', '\\u003c')
        (tmp / 'provenance.html').write_text('<script id="report-provenance" type="application/json">' + record + '</script>')
        env = dict(os.environ, HEALTH_REPORT_PROJECT=str(REPO), R_PROFILE_USER=str(REPO / '.Rprofile'))
        subprocess.run([quarto, 'render', 'report.qmd', '--to', fmt], cwd=tmp, env=env, check=True)
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(tmp / f'report.{fmt}', output)
        write_json(output.with_suffix(f'.{fmt}.provenance.json'), provenance)


def release(dest, formats):
    dest = Path(dest)
    paths = [dest / f'report.{f}' for f in formats] + [dest / f'report.{f}.provenance.json' for f in formats]
    source = dest / 'render-source'
    source.mkdir(parents=True, exist_ok=True)
    for n in BUNDLE_FILES:
        shutil.copyfile(dest / 'data' / n, source / n)
    shutil.copyfile(HERE / 'templates/request_report.qmd', source / 'report.qmd')
    record = json.loads((dest / f'report.{formats[0]}.provenance.json').read_text())
    write_json(source / 'provenance.json', record)
    (source / 'provenance.html').write_text('<script id="report-provenance" type="application/json">' +
                                          json.dumps(record).replace('<', '\\u003c') + '</script>')
    paths += sorted((dest / 'data').glob('*')) + sorted(source.glob('*'))
    write_json(dest / 'result.json', {'status': 'success', 'request': json.loads((dest / 'data/request.json').read_text()),
                                    'artifacts': [{'path': p.relative_to(dest).as_posix(), 'sha256': digest(p)} for p in paths if p.is_file()]})


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='command', required=True)
    p = sub.add_parser('seal'); p.add_argument('--prepared', required=True)
    p = sub.add_parser('analyse')
    for n in ['prepared', 'request', 'snapshot', 'dest']: p.add_argument('--' + n, required=True)
    p = sub.add_parser('render')
    for n in ['bundle', 'format', 'output']: p.add_argument('--' + n, required=True)
    p.add_argument('--quarto', default='quarto')
    p = sub.add_parser('release'); p.add_argument('--dest', required=True); p.add_argument('--formats', nargs='+', required=True)
    args = ap.parse_args()
    if args.command == 'seal': seal_prepared(args.prepared)
    elif args.command == 'analyse': analyse_request(args.prepared, args.request, args.snapshot, args.dest)
    elif args.command == 'render': render(args.bundle, args.format, args.output, args.quarto)
    else: release(args.dest, args.formats)
