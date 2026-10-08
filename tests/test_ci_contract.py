"""Phase 6: CI release gates are structurally enforced."""
import json
import re
from pathlib import Path

import pytest
import yaml

from verify_release import verify

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((ROOT / '.github/workflows').glob('*.yml'))


def workflow(name):
    return yaml.safe_load((ROOT / '.github/workflows' / name).read_text())


def test_every_action_is_pinned_to_a_commit_sha():
    for path in WORKFLOWS:
        for ref in re.findall(r'uses:\s*(\S+)', path.read_text()):
            assert re.fullmatch(r'[\w.-]+/[\w./-]+@[0-9a-f]{40}', ref), f'{path.name}: {ref}'


def test_dependabot_updates_github_actions():
    config = yaml.safe_load((ROOT / '.github/dependabot.yml').read_text())
    assert any(u['package-ecosystem'] == 'github-actions' for u in config['updates'])


def test_validate_has_fast_and_full_gates_on_push_and_pr():
    wf = workflow('validate.yml')
    triggers = wf.get('on', wf.get(True))  # PyYAML parses bare `on` as True
    assert 'push' in triggers and 'pull_request' in triggers
    jobs = wf['jobs']
    assert {'fast', 'secrets', 'container', 'full'} <= set(jobs)
    assert jobs['full']['needs'] == 'fast' and jobs['container']['needs'] == 'fast'
    fast = ' '.join(s.get('run', '') for s in jobs['fast']['steps'])
    for command in ['ruff check', 'pytest', 'snakemake --dry-run']:
        assert command in fast
    assert 'secret_scan.sh' in ' '.join(s.get('run', '') for s in jobs['secrets']['steps'])
    assert jobs['secrets']['steps'][0]['with']['fetch-depth'] == 0


@pytest.mark.parametrize('name,job', [('validate.yml', 'full'), ('update-lyme-data.yml', 'update-and-build')])
def test_artifacts_are_uploaded_only_after_all_verification(name, job):
    steps = workflow(name)['jobs'][job]['steps']
    upload = next(i for i, s in enumerate(steps) if 'upload-artifact' in s.get('uses', ''))
    runs = [s.get('run', '') for s in steps[:upload]]
    for gate in ['snakemake --cores 2', 'check_outputs.py', 'verify_release.py', 'shiny_smoke.R']:
        assert any(gate in r for r in runs), f'{name}: {gate} must precede upload'
    assert not any('upload-artifact' in s.get('uses', '') for s in steps[:upload])
    assert all('continue-on-error' not in s for s in steps)


def test_lint_and_secret_scan_are_pinned():
    assert re.fullmatch(r'ruff==\d+\.\d+\.\d+\n', (ROOT / 'scripts/ci/requirements-lint.txt').read_text())
    scan = (ROOT / 'scripts/ci/secret_scan.sh').read_text()
    assert re.search(r'expected_sha256="[0-9a-f]{64}"', scan) and 'sha256sum --check' in scan
    assert '[tool.ruff.lint]' in (ROOT / 'pyproject.toml').read_text()


def fake_release(tmp_path):
    """Smallest release tree accepted by verify_release, built from real helpers."""
    from common import digest
    from publish import TEMPLATE, HERE
    out = tmp_path / 'results'
    folder = out / 'reports' / 'demo'
    (folder / 'data').mkdir(parents=True)
    (folder / 'data/stakeholder.json').write_text('{"id": "demo"}\n')
    (folder / 'data/metrics.csv').write_text('metric_id,value\nx,1\n')
    rec = {'analysis_bundle': {'files': {n: digest(folder / 'data' / n) for n in ['metrics.csv', 'stakeholder.json']}},
           'output': {'shared_template_sha256': digest(HERE / TEMPLATE)},
           'stakeholder': {'parameters_sha256': digest(folder / 'data/stakeholder.json')}}
    for side in ['provenance.json', 'provenance.pdf.json']:
        (folder / side).write_text(json.dumps(rec))
    embed = '<script type="application/json" id="report-provenance">' + json.dumps(rec) + '</script>'
    (folder / 'report.html').write_text(f'<h2 id="top">x</h2><a href="methods.html#sel">m</a><a href="#top">t</a>'
                                        f'<a href="provenance.json">p</a><a href="https://example.org">e</a>{embed}')
    (folder / 'methods.html').write_text(f'<section id="sel"></section><a href="report.html">r</a>{embed}')
    artifacts = {p.relative_to(out).as_posix(): digest(p) for p in out.rglob('*') if p.is_file()}
    (out / 'release.json').write_text(json.dumps({'artifacts': artifacts}))
    return out, folder


def test_verify_release_accepts_consistent_release(tmp_path):
    out, _ = fake_release(tmp_path)
    assert verify(out) == []


@pytest.mark.parametrize('damage,message', [
    ('tamper_artifact', 'hash mismatch'),
    ('unrecorded_artifact', 'not recorded'),
    ('tamper_bundle', 'bundle hash mismatch'),
    ('broken_link', 'broken link'),
    ('missing_anchor', 'missing anchor'),
    ('remote_asset', 'remote asset'),
    ('embedded_drift', 'embedded provenance differs'),
])
def test_verify_release_rejects_damage(tmp_path, damage, message):
    out, folder = fake_release(tmp_path)
    report = folder / 'report.html'
    if damage == 'tamper_artifact':
        (folder / 'provenance.pdf.json').write_text('{}')
    elif damage == 'unrecorded_artifact':
        (folder / 'extra.txt').write_text('x')
    elif damage == 'tamper_bundle':
        (folder / 'data/metrics.csv').write_text('metric_id,value\nx,2\n')
    elif damage == 'broken_link':
        report.write_text(report.read_text().replace('provenance.json">', 'missing.json">'))
    elif damage == 'missing_anchor':
        report.write_text(report.read_text().replace('#sel', '#nowhere'))
    elif damage == 'remote_asset':
        report.write_text(report.read_text() + '<script src="https://cdn.example.org/x.js"></script>')
    elif damage == 'embedded_drift':
        m = folder / 'methods.html'
        m.write_text(m.read_text().replace('"parameters_sha256"', '"parameters_sha256_x"'))
    assert any(message in e for e in verify(out)), verify(out)
