#!/usr/bin/env python3
"""Verify a completed build: one HTML report per configured audience, each with provenance.

Run after `snakemake` (CI does this). Exits nonzero on any missing or inconsistent output.
"""
import argparse
import json
import re
import sys
from pathlib import Path

import yaml

REQUIRED = {
    'schema', 'rendered_at_utc', 'output', 'stakeholder', 'filters', 'effective_parameters',
    'data', 'analysis_bundle', 'quality_checks', 'software', 'code',
}
EMBED = re.compile(r'<script type="application/json" id="report-provenance">(.*?)</script>', re.S)


def check(out, config):
    stakeholders = yaml.safe_load(Path(config).read_text())['stakeholders']
    reports = Path(out) / 'reports'
    errors = []
    built = sorted(p.parent.name for p in reports.glob('*/report.html'))
    if built != sorted(stakeholders):
        errors.append(f'Expected HTML reports for {sorted(stakeholders)}, found {built}')
    layouts = {}
    for s in stakeholders:
        folder = reports / s
        for doc in ['report.html', 'methods.html']:
            html = folder / doc
            if not html.is_file():
                errors.append(f'{s}: missing {doc}'); continue
            text = html.read_text(encoding='utf-8')
            m = EMBED.search(text)
            if not m:
                errors.append(f'{s}/{doc}: no embedded provenance'); continue
            embedded = json.loads(m.group(1).replace('<\\/', '</'))
            if embedded.get('stakeholder', {}).get('id') != s:
                errors.append(f'{s}/{doc}: embedded provenance names another stakeholder')
            if 'table-filter' not in text:
                errors.append(f'{s}/{doc}: interactive table script missing')
        for name, fmt in [('provenance.json', 'html'), ('provenance.pdf.json', 'pdf')]:
            p = folder / name
            if not p.is_file():
                errors.append(f'{s}: missing {name}'); continue
            rec = json.loads(p.read_text())
            if missing := REQUIRED - set(rec):
                errors.append(f'{s}/{name}: missing keys {sorted(missing)}')
            if rec.get('output', {}).get('format') != fmt:
                errors.append(f'{s}/{name}: wrong format')
            if rec.get('stakeholder', {}).get('id') != s:
                errors.append(f'{s}/{name}: wrong stakeholder')
            if not rec.get('data', {}).get('snapshot_id'):
                errors.append(f'{s}/{name}: no snapshot id')
            if fmt == 'html':
                p_ = rec['stakeholder'].get('presentation') or {}
                layouts[s] = (p_.get('layout'), p_.get('detail_level'))
                root = rec['data'].get('canonical_root') or rec['data'].get('snapshot_manifest') or ''
                if root.split('/')[0] == 'Data':
                    errors.append(f'{s}: provenance points to removed Data/ root')
    if len(set(layouts.values())) != len(layouts):
        errors.append(f'Audiences do not have distinct presentations: {layouts}')
    return errors


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='results')
    ap.add_argument('--config', default='workflow/config.yaml')
    a = ap.parse_args()
    errors = check(a.out, a.config)
    for e in errors:
        print('ERROR:', e, file=sys.stderr)
    if errors:
        sys.exit(1)
    print('Audience outputs and provenance verified')
