"""Phase 7: release documentation stays accurate and navigable."""
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DOCS = [ROOT / 'README.md', ROOT / 'RELEASE_NOTES.md', ROOT / 'CONTRIBUTING.md', *sorted((ROOT / 'docs').glob('*.md'))]
LINK = re.compile(r'(?<!\!)\[[^\]]+\]\(([^)\s]+)\)')


def slug(heading):
    s = re.sub(r'[^\w\- ]', '', heading.strip().lower()).replace(' ', '-')
    return s


def anchors(path):
    return {slug(m.group(1)) for m in re.finditer(r'^#{1,6}\s+(.*)$', path.read_text(), re.M)}


def test_relative_links_and_anchors_resolve():
    errors = []
    for doc in DOCS:
        for target in LINK.findall(doc.read_text()):
            if re.match(r'[a-z]+:', target):
                continue
            path, _, fragment = target.partition('#')
            dest = (doc.parent / path).resolve() if path else doc
            if not dest.exists():
                errors.append(f'{doc.name}: {target}')
            elif fragment and dest.suffix == '.md' and fragment not in anchors(dest):
                errors.append(f'{doc.name}: missing anchor {target}')
    assert not errors, errors


def test_readme_documents_one_command_and_expected_outputs():
    readme = (ROOT / 'README.md').read_text()
    config = yaml.safe_load((ROOT / 'workflow/config.yaml').read_text())
    assert 'snakemake --cores 2' in readme and 'run_all.sh' in readme
    for sid in config['stakeholders']:
        assert f'results/reports/{sid}/report.html' in readme
    for required in ['docs/limitations.md', 'docs/architecture.md', 'CITATION.cff', 'data/README.md']:
        assert required in readme


def test_run_all_is_a_snakemake_wrapper_without_retired_paths():
    script = (ROOT / 'scripts/health_pipeline/run_all.sh').read_text()
    assert 'snakemake' in script and 'Data' not in script.replace('data_root', '')
    out = subprocess.run(['bash', str(ROOT / 'scripts/health_pipeline/run_all.sh'), '', '', '--dry-run', '--forceall'],
                         capture_output=True, text=True, env={'PATH': str(Path(sys.executable).parent) + ':/usr/bin:/bin'})
    assert out.returncode == 0, out.stderr[-500:]
    for sid in yaml.safe_load((ROOT / 'workflow/config.yaml').read_text())['stakeholders']:
        assert f'results/reports/{sid}/report.html' in out.stdout


def test_citation_metadata_is_valid():
    cff = yaml.safe_load((ROOT / 'CITATION.cff').read_text())
    for key in ['cff-version', 'message', 'title', 'authors', 'repository-code', 'abstract']:
        assert cff.get(key), key
    assert cff['authors'] and cff['repository-code'].startswith('https://github.com/')
    assert any(r.get('type') == 'dataset' for r in cff['references'])


def test_data_terms_and_limitations_are_stated():
    data = (ROOT / 'data/README.md').read_text()
    assert 'source attribution' in data and 'Federal Office of Public Health' in data
    assert 'Data/' in data  # retired root remains documented
    limits = (ROOT / 'docs/limitations.md').read_text().lower()
    for topic in ['not infections', 'descriptive', 'influenza', 'national totals', 'revised', 'licence']:
        assert topic in limits, topic


def test_documented_headline_numbers_match_provenance_free_inputs():
    """Docs quote +124% / +21% / -3%; keep them tied to the audience smoke test."""
    smoke = (ROOT / 'tests/dashboard_smoke.R').read_text()
    docs = ((ROOT / 'docs/demo.md').read_text() + (ROOT / 'docs/limitations.md').read_text()).replace('\u2212', '-')
    for value in ['+124%', '+21%', '-3%']:
        assert value in smoke
        assert value in docs
