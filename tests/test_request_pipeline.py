"""Request contracts, scientific selection and cache integrity regression tests."""
import json
import os
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


@pytest.fixture
def provenance_checkout(tmp_path, monkeypatch):
    import subprocess
    import request_pipeline
    repo = tmp_path / 'checkout'
    repo.mkdir()
    monkeypatch.setenv('GIT_CONFIG_NOSYSTEM', '1')
    monkeypatch.setenv('GIT_CONFIG_GLOBAL', os.devnull)
    monkeypatch.delenv('GITHUB_ACTIONS', raising=False)
    subprocess.run(['git', 'init', '-q', str(repo)], check=True)
    subprocess.run(['git', '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                    'commit', '-q', '--allow-empty', '-m', 'Fixture'], cwd=repo, check=True)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    monkeypatch.setattr(request_pipeline, 'REPO', repo)
    return repo, commit


def test_commit_on_runner_owned_mount(provenance_checkout, monkeypatch):
    import subprocess
    from request_pipeline import source_commit
    repo, expected = provenance_checkout
    monkeypatch.setenv('GIT_TEST_ASSUME_DIFFERENT_OWNER', '1')
    denied = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=repo, capture_output=True, text=True)
    assert denied.returncode != 0 and 'dubious ownership' in denied.stderr
    assert source_commit() == expected


def test_commit_matches_actions_run(provenance_checkout, monkeypatch):
    from request_pipeline import source_commit
    _, expected = provenance_checkout
    monkeypatch.setenv('GITHUB_ACTIONS', 'true')
    monkeypatch.setenv('GITHUB_SHA', expected)
    assert source_commit() == expected
    monkeypatch.setenv('GITHUB_SHA', '0' * 40)
    with pytest.raises(RuntimeError, match='does not match'):
        source_commit()


def test_actions_missing_checkout_blocks_report(tmp_path, monkeypatch):
    import request_pipeline
    monkeypatch.setattr(request_pipeline, 'REPO', tmp_path)
    monkeypatch.setenv('GITHUB_ACTIONS', 'true')
    with pytest.raises(RuntimeError, match='Cannot identify'):
        request_pipeline.source_commit()
    monkeypatch.delenv('GITHUB_ACTIONS')
    assert request_pipeline.source_commit() == 'unavailable'


def test_preparation_identity_changes_with_inputs_and_environment(request_project, monkeypatch):
    from inventory import build
    from request_pipeline import preparation_key
    raw, prepared, _, _ = request_project
    sid = build(raw, prepared)['snapshot_id']
    key = preparation_key(sid)
    data = raw / 'alpha' / 'data.csv'
    frame = pd.read_csv(data)
    frame.loc[0, 'value'] = 6
    frame.to_csv(data, index=False)
    new_sid = build(raw, prepared)['snapshot_id']
    assert new_sid != sid
    assert preparation_key(new_sid) != key
    monkeypatch.setenv('REQUEST_ENVIRONMENT_IMAGE', 'different-tested-image')
    assert preparation_key(sid) != key
    import request_pipeline
    before_code_change = preparation_key(sid)
    original_digest = request_pipeline.digest
    monkeypatch.setattr(request_pipeline, 'digest', lambda p: 'changed' if Path(p).name == 'harmonise.py' else original_digest(p))
    assert preparation_key(sid) != before_code_change


def test_fresh_runner_reuses_preparation_for_new_selection(request_project, tmp_path):
    import subprocess, sys
    from request_pipeline import REPO, cache_plan, PREP_FILES
    raw, _, request, _ = request_project
    config = tmp_path / 'config.json'
    out = tmp_path / 'runner-output'
    config.write_text(json.dumps({'data_root': str(raw), 'out': str(out)}))
    plan = cache_plan(config)
    request.write_text(json.dumps({'schema_version': '1.0', 'request_id': 'first',
                                  'audience': 'public_health_expert', 'datasets': ['alpha'], 'formats': ['html']}))
    # Use repository paths for code; each output root has independent rule outputs.
    command = [sys.executable, '-m', 'snakemake', 'request_analyse', '--cores', '1',
               '--config', f'request_file={request}', f'snapshot_manifest={plan["snapshot"]}', f'out={out}']
    cold = subprocess.run(command, cwd=REPO, text=True, capture_output=True)
    assert cold.returncode == 0, cold.stdout + cold.stderr
    assert 'localrule request_prepare:' in cold.stderr
    prepared = Path(plan['prepared'])
    saved = tmp_path / 'saved-preparation'
    shutil.copytree(prepared, saved)
    # Restore into another output root, with no Snakemake metadata for these paths.
    second_out = tmp_path / 'second-runner'
    restored = second_out / 'cache' / 'prepared' / prepared.name
    shutil.copytree(saved, restored)
    for p in restored.iterdir():
        os.utime(p, (1, 1))
    before = {n: (restored / n).stat().st_mtime_ns for n in PREP_FILES + ['prepared.json']}
    request.write_text(json.dumps({'schema_version': '1.0', 'request_id': 'second',
                                  'audience': 'researcher', 'datasets': ['beta', 'gamma'], 'formats': ['html']}))
    command[-1] = f'out={second_out}'
    warm = subprocess.run(command, cwd=REPO, text=True, capture_output=True)
    assert warm.returncode == 0, warm.stdout + warm.stderr
    assert 'localrule request_prepare:' not in warm.stderr
    assert before == {n: (restored / n).stat().st_mtime_ns for n in before}
    series = next((second_out / 'requests').glob('*/data/series.csv'))
    assert set(pd.read_csv(series).dataset) == {'beta', 'gamma'}
    with pytest.raises(ValueError, match='different snapshot'):
        verify_prepared(restored, 'wrong-snapshot')
