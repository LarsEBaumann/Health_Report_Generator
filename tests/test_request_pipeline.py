"""Request contracts, scientific selection and cache integrity regression tests."""
import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from harmonise import main as harmonise
from request_pipeline import read_request, analyse_request, seal_prepared, verify_prepared, catalogue


@pytest.fixture
def request_project(tmp_path):
    raw = tmp_path / 'raw'
    for name, offset in [('alpha', 0), ('beta', 10), ('gamma', 20)]:
        p = raw / name
        p.mkdir(parents=True)
        meta = {'metaVariables': {'topic': 'same_topic', 'source': name, 'valueCategory': {'column': 'measure'}},
                'temporalVariables': {'column': 'period', 'typeColumn': 'period_type'},
                'groupingVariables': {'georegion': {'column': 'georegion', 'typeColumn': 'georegion_type'},
                                      'sex': {'column': 'sex', 'allValue': 'all'}},
                'valueVariables': {'value': {}}, 'entryVariables': {'dataComplete': {}}}
        (p / 'metadata.json').write_text(json.dumps(meta))
        pd.DataFrame([{'measure': 'cases', 'period': f'2025-M{m:02d}', 'period_type': 'month',
                       'georegion': 'CH', 'georegion_type': 'country', 'sex': 'all',
                       'value': v + offset if v is not None else None, 'dataComplete': 'TRUE'}
                      for m, v in [(1, 5), (3, None), (4, 8)]]).to_csv(p / 'data.csv', index=False)
    return raw, tmp_path / 'prepared', tmp_path / 'request.json', tmp_path / 'bundle'


def prepare(project, datasets=None, audience='public_health_expert'):
    raw, prepared, request, dest = project
    harmonise([str(raw), '--out', str(prepared)])
    seal_prepared(prepared)
    request.write_text(json.dumps({'schema_version': '1.0', 'request_id': 'test', 'audience': audience,
                                  'datasets': datasets or ['alpha'], 'formats': ['html']}))
    return prepared, request, prepared / 'snapshot.json', dest


def test_multiple_sources_same_topic_and_gaps(request_project):
    args = prepare(request_project, ['alpha', 'beta', 'gamma'])
    analyse_request(*args)
    series = pd.read_csv(args[-1] / 'series.csv')
    assert set(series.dataset) == {'alpha', 'beta', 'gamma'}
    assert series.metric_id.is_unique
    alpha = series[series.dataset == 'alpha']
    assert alpha.observation_status.tolist() == ['observed', 'missing_period', 'missing_value', 'observed']
    assert alpha.value.dropna().tolist() == [5, 8]
    assert pd.isna(alpha.iloc[1].source_row)
    lineage = pd.read_csv(args[-1] / 'lineage.csv')
    assert len(lineage) == 9
    assert lineage.source_row.tolist()[:3] == [2, 3, 4]


def test_audience_does_not_change_values(request_project):
    args = prepare(request_project)
    analyse_request(*args)
    first = (args[-1] / 'series.csv').read_bytes()
    req = json.loads(args[1].read_text()); req['audience'] = 'general_public'
    args[1].write_text(json.dumps(req))
    analyse_request(*args)
    assert (args[-1] / 'series.csv').read_bytes() == first


@pytest.mark.parametrize('field,value', [('audience', 'unknown'), ('formats', ['shiny']), ('datasets', []),
                                        ('datasets', ['alpha', 'alpha']), ('schema_version', '2.0'),
                                        ('request_id', '../escape'), ('extra', True)])
def test_invalid_requests(request_project, field, value):
    args = prepare(request_project)
    req = json.loads(args[1].read_text()); req[field] = value
    args[1].write_text(json.dumps(req))
    with pytest.raises(ValueError, match='Invalid request'): read_request(args[1])


def test_duplicate_json_fields(request_project):
    p = request_project[2]; p.write_text('{"audience":"researcher","audience":"general_public"}')
    with pytest.raises(ValueError, match='Duplicate JSON'): read_request(p)


def test_unknown_dataset_not_silently_dropped(request_project):
    args = prepare(request_project, ['alpha', 'unknown'])
    with pytest.raises(ValueError, match='Unknown dataset'): analyse_request(*args)
    assert not (args[-1] / 'bundle.json').exists()


def test_unselected_quarantine_does_not_block(request_project):
    (request_project[0] / 'beta/metadata.json').write_text('{broken')
    args = prepare(request_project)
    analyse_request(*args)
    req = json.loads(args[1].read_text()); req['datasets'] = ['beta']; args[1].write_text(json.dumps(req))
    with pytest.raises(ValueError, match='quarantined'): analyse_request(*args)
    assert not (args[-1] / 'bundle.json').exists()


def test_selected_negative_value_blocks(request_project):
    p = request_project[0] / 'alpha/data.csv'; d = pd.read_csv(p); d.loc[0, 'value'] = -1; d.to_csv(p, index=False)
    args = prepare(request_project)
    with pytest.raises(ValueError, match='blocking'): analyse_request(*args)


def test_unsupported_measure_is_explicit(request_project):
    p = request_project[0] / 'alpha/data.csv'; d = pd.read_csv(p); d['measure'] = 'positivity'; d.to_csv(p, index=False)
    args = prepare(request_project)
    with pytest.raises(ValueError, match='unsupported measure'): analyse_request(*args)


def test_exact_duplicate_folders_keep_one_dataset(request_project):
    shutil.copytree(request_project[0] / 'alpha', request_project[0] / 'alpha (1)')
    args = prepare(request_project)
    analyse_request(*args)
    assert len(pd.read_csv(args[-1] / 'series.csv')) == 4


def test_cache_and_snapshot_tamper(request_project):
    args = prepare(request_project)
    p = args[0] / 'role_log.csv'; p.write_text(p.read_text() + '\n')
    with pytest.raises(ValueError, match='integrity'): verify_prepared(args[0])
    seal_prepared(args[0])
    manifest = json.loads(args[2].read_text())
    raw = args[0] / manifest['snapshot_path'] / 'alpha/data.csv'
    raw.write_text(raw.read_text() + '\n')
    with pytest.raises(ValueError, match='checksum'): analyse_request(*args)


def test_ambiguous_totals_block(request_project):
    p = request_project[0] / 'alpha'
    meta = json.loads((p / 'metadata.json').read_text())
    meta['groupingVariables']['sex']['typeValues'] = {'other': {'allValue': 'total'}}
    (p / 'metadata.json').write_text(json.dumps(meta))
    d = pd.read_csv(p / 'data.csv')
    pd.concat([d, d.assign(sex='total')]).to_csv(p / 'data.csv', index=False)
    args = prepare(request_project)
    with pytest.raises(ValueError, match='ambiguous multiple totals'): analyse_request(*args)


def test_default_workflow_target_builds_request(request_project):
    import subprocess, sys
    from request_pipeline import REPO
    args = prepare(request_project)
    proc = subprocess.run([sys.executable, '-m', 'snakemake', '--dry-run', '--cores', '1', '--config',
                           f'request_file={args[1]}', f'snapshot_manifest={args[2]}',
                           f'out={args[-1].parent / "workflow-output"}'], cwd=REPO, text=True, capture_output=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert 'request_render' in proc.stdout
    assert 'request_analyse' in proc.stdout
    assert 'request_prepare' in proc.stdout
