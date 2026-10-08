"""Phase 5: one shared report source, three parameterised audiences, provenance wired in."""
import json
import re
from pathlib import Path

import jsonschema
import pytest
import yaml

from analyse import load_config
from publish import build_provenance, package
import render_selected
from test_pipeline import project, run  # noqa: F401  (pytest fixture reuse)

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / 'scripts/health_pipeline'
STAKEHOLDERS = P / 'config/stakeholders'
AUDIENCES = ['researcher', 'health_institution', 'public']
# Keys allowed to differ between audiences: communication, not analysis.
PRESENTATION_KEYS = {'id', 'title', 'question', 'outputs', 'presentation'}


def config():
    return yaml.safe_load((ROOT / 'workflow/config.yaml').read_text())


def stakeholder(sid):
    return json.loads((STAKEHOLDERS / f'{sid}.json').read_text())


def test_default_build_enables_exactly_three_audiences():
    assert config()['stakeholders'] == AUDIENCES


@pytest.mark.parametrize('sid', AUDIENCES)
def test_stakeholder_configs_validate_against_schema(sid):
    schema = json.loads((ROOT / 'workflow/config.schema.json').read_text())
    cfg = stakeholder(sid)
    jsonschema.validate(cfg, schema)
    assert load_config(STAKEHOLDERS / f'{sid}.json')['id'] == sid
    assert set(cfg['presentation']) == {'display_name', 'layout', 'detail_level', 'version'}


def test_audiences_have_distinct_presentation_and_sections():
    cfgs = [stakeholder(s) for s in AUDIENCES]
    layouts = {(c['presentation']['layout'], c['presentation']['detail_level']) for c in cfgs}
    assert layouts == {('technical', 'full'), ('dashboard', 'monitoring'), ('editorial', 'plain_language')}
    assert len({tuple(c['outputs']) for c in cfgs}) == len(cfgs)
    # Uncertainty context is never removed for non-technical audiences.
    for c in cfgs:
        assert {'headline', 'quality', 'sources'} <= set(c['outputs'])


def test_audiences_share_identical_analytic_parameters():
    """Findings must agree across audiences; only communication differs."""
    reference = {k: v for k, v in stakeholder('public_health_expert').items() if k not in PRESENTATION_KEYS}
    for sid in AUDIENCES:
        analytic = {k: v for k, v in stakeholder(sid).items() if k not in PRESENTATION_KEYS}
        assert analytic == reference, sid


def test_single_shared_report_source():
    reports = sorted(p.name for p in P.rglob('*.qmd') if 'example_output' not in p.parts)
    assert reports == ['methods.qmd', 'report_public_health_expert.qmd']
    snakefile = (ROOT / 'Snakefile').read_text()
    assert snakefile.count('report_public_health_expert.qmd') == 1  # declared once as SHARED_TEMPLATE
    assert 'SHARED_TEMPLATE' in snakefile.split('PRESENTATION_CODE =')[1].split(']')[0]
    assert "{s}" not in re.search(r"SHARED_TEMPLATE = (.*)", snakefile).group(1)


def test_shared_template_is_packaged_for_every_audience(project, tmp_path):  # noqa: F811
    bundle = run(project)
    package(bundle, tmp_path / 'app')
    assert (tmp_path / 'app/report.qmd').read_bytes() == (P / 'report_public_health_expert.qmd').read_bytes()
    assert (tmp_path / 'app/audience_reports.R').is_file()


def test_active_workflow_uses_canonical_data_root_only():
    assert config()['data_root'] == 'data/reference'
    for path in ['Snakefile', 'workflow/config.yaml', *map(str, (ROOT / '.github/workflows').glob('*.yml'))]:
        text = (ROOT / path).read_text()
        assert not re.search(r"(?<![\w/])Data/", text), path


def test_every_audience_has_provenance_wired_in():
    snakefile = (ROOT / 'Snakefile').read_text()
    for rule, name in [('render_html', 'provenance.json'), ('render_pdf', 'provenance.pdf.json')]:
        body = snakefile.split(f'rule {rule}:')[1].split('\nrule ')[0]
        assert name in body and '--provenance' in body and '--data-root' in body
    assert 'PROVENANCE' in snakefile.split('rule all:')[1].split('\n')[1]
    for template in [P / 'report_public_health_expert.qmd', P / 'templates/methods.qmd']:
        assert 'provenance_script()' in template.read_text()


def test_provenance_record_contents(project):  # noqa: F811
    bundle = run(project)
    cfg = json.loads((bundle / 'stakeholder.json').read_text())
    rec = build_provenance(bundle, 'html', quarto='quarto-not-installed', data_root='data/reference',
                           workflow_config={'path': 'workflow/config.yaml', 'sha256': 'x'})
    assert rec['schema'] == 'health-report-provenance/1.0'
    assert rec['stakeholder']['id'] == cfg['id']
    assert rec['effective_parameters'] == cfg
    assert rec['filters']['geography'] == cfg['geography'] and rec['filters']['years'] == cfg['years']
    assert rec['data']['canonical_root'] == 'data/reference'
    assert rec['data']['snapshot_id'] == json.loads((bundle / 'bundle.json').read_text())['snapshot_id']
    assert rec['data']['datasets_used'] == 2
    assert rec['output']['shared_template'].endswith('report_public_health_expert.qmd')
    assert rec['rendered_at_utc'] and rec['software']['python']
    assert 'git_commit' in rec['code']
    json.dumps(rec, allow_nan=False)


def test_selected_report_lineage_prefers_researcher_then_legacy(tmp_path):
    for sid in ['public_health_expert', 'researcher']:
        d = tmp_path / 'reports' / sid / 'data'
        d.mkdir(parents=True)
        (d / 'series.csv').write_text('x\n')
        (d / 'selection.csv').write_text('x\n')
        assert render_selected.lineage_bundle(tmp_path) == d
