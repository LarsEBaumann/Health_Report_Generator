#!/usr/bin/env python3
"""Release gate: verify hashes, provenance and rendered HTML links of a completed build.

Run after `snakemake` and `check_outputs.py`. Exits nonzero on any failure, so CI uploads
artifacts only for a release whose recorded hashes match the files actually produced.

Checks
- every artifact hash in release.json matches the file on disk, and every file is recorded;
- every provenance sidecar's analysis-bundle hashes match the audience's data/ files and its
  shared-template hash matches the source template;
- the provenance embedded in each HTML page equals its provenance.json sidecar;
- every local link/asset in rendered HTML resolves (file and #anchor), and HTML pages load
  no remote scripts, stylesheets or images.
"""
import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from common import digest

HERE = Path(__file__).resolve().parent
EMBED = re.compile(r'<script type="application/json" id="report-provenance">(.*?)</script>', re.S)


class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self.assets, self.ids = [], [], set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get('id'):
            self.ids.add(a['id'])
        if tag == 'a' and a.get('name'):
            self.ids.add(a['name'])
        if tag == 'a' and a.get('href'):
            self.links.append(a['href'])
        if tag in ('img', 'script', 'iframe', 'source') and a.get('src'):
            self.assets.append(a['src'])
        if tag == 'link' and a.get('href') and 'stylesheet' in (a.get('rel') or ''):
            self.assets.append(a['href'])


def parse(path):
    p = Links()
    p.feed(path.read_text(encoding='utf-8'))
    return p


def check_release(out):
    errors = []
    release = json.loads((out / 'release.json').read_text())
    recorded = release.get('artifacts', {})
    for rel, expected in recorded.items():
        f = out / rel
        if not f.is_file():
            errors.append(f'release.json lists missing artifact {rel}')
        elif digest(f) != expected:
            errors.append(f'hash mismatch for {rel}')
    actual = {p.relative_to(out).as_posix() for p in out.rglob('*')
              if p.is_file() and 'snapshots' not in p.parts and p.name != 'release.json'}
    if unrecorded := sorted(actual - set(recorded)):
        errors.append(f'artifacts not recorded in release.json: {unrecorded[:5]}')
    return errors


def check_provenance(folder):
    errors = []
    name = folder.name
    template = HERE / 'report_public_health_expert.qmd'
    for side in ['provenance.json', 'provenance.pdf.json']:
        try:
            rec = json.loads((folder / side).read_text())
            rec['analysis_bundle']['files'], rec['output']['shared_template_sha256'], rec['stakeholder']['parameters_sha256']
        except (OSError, ValueError, KeyError, TypeError) as e:
            errors.append(f'{name}/{side}: unreadable or incomplete provenance ({type(e).__name__})')
            continue
        for f, expected in rec['analysis_bundle']['files'].items():
            p = folder / 'data' / f
            if not p.is_file() or digest(p) != expected:
                errors.append(f'{name}/{side}: bundle hash mismatch for {f}')
        if rec['output']['shared_template_sha256'] != digest(template):
            errors.append(f'{name}/{side}: shared template hash does not match source')
        if rec['stakeholder']['parameters_sha256'] != digest(folder / 'data/stakeholder.json'):
            errors.append(f'{name}/{side}: parameter hash mismatch')
    try:
        sidecar = json.loads((folder / 'provenance.json').read_text())
    except (OSError, ValueError):
        return errors
    for doc in ['report.html', 'methods.html']:
        m = EMBED.search((folder / doc).read_text(encoding='utf-8'))
        if not m or json.loads(m.group(1).replace('<\\/', '</')) != sidecar:
            errors.append(f'{name}/{doc}: embedded provenance differs from provenance.json')
    return errors


def check_links(folder):
    errors = []
    pages = {p.name: parse(p) for p in sorted(folder.glob('*.html'))}
    for page, parsed in pages.items():
        for src in parsed.assets:
            scheme = urlsplit(src).scheme
            if scheme in ('http', 'https') or src.startswith('//'):
                errors.append(f'{folder.name}/{page}: remote asset {src[:80]}')
            elif scheme == '' and not (folder / unquote(urlsplit(src).path)).is_file():
                errors.append(f'{folder.name}/{page}: missing asset {src[:80]}')
        for href in parsed.links:
            u = urlsplit(href)
            if u.scheme or href.startswith('//'):
                continue  # external links are not fetched in CI
            target = page if not u.path else unquote(u.path)
            f = folder / target
            if not f.is_file():
                errors.append(f'{folder.name}/{page}: broken link {href}')
            elif u.fragment and f.suffix == '.html':
                ids = pages[target].ids if target in pages else parse(f).ids
                if u.fragment not in ids:
                    errors.append(f'{folder.name}/{page}: missing anchor {href}')
    return errors


def verify(out):
    out = Path(out)
    errors = check_release(out)
    for folder in sorted(p.parent for p in (out / 'reports').glob('*/provenance.json')):
        errors += check_provenance(folder) + check_links(folder)
    return errors


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='results')
    errors = verify(ap.parse_args().out)
    for e in errors:
        print('ERROR:', e, file=sys.stderr)
    if errors:
        sys.exit(1)
    print('Release hashes, provenance and rendered links verified')
