"""Exercise the request workflow inside the image, with networking disabled by CI.

Run from the repository root. No dependencies are installed by this script.
Successful output is kept under results/request-image-smoke for inspection.
"""
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/request-image-smoke'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args):
    print('+', ' '.join(map(str, args)), flush=True)
    started = time.monotonic()
    result = subprocess.run(args, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    print(result.stdout, flush=True)
    if result.returncode:
        raise RuntimeError(f'Command exited {result.returncode}: {args}')
    return result.stdout, round(time.monotonic() - started, 3)


class Images(HTMLParser):
    def __init__(self):
        super().__init__()
        self.sources = []

    def handle_starttag(self, tag, attrs):
        if tag == 'img':
            self.sources.append(dict(attrs).get('src', ''))


def verify_result(result_path, request):
    root = result_path.parent
    result = json.loads(result_path.read_text())
    assert result['status'] == 'success'
    assert result['request'] == request
    assert json.loads((root / 'data/request.json').read_text()) == request
    listed = {a['path']: a['sha256'] for a in result['artifacts']}
    for fmt in request['formats']:
        assert f'report.{fmt}' in listed
        assert f'report.{fmt}.provenance.json' in listed
        provenance = json.loads((root / f'report.{fmt}.provenance.json').read_text())
        assert provenance['request'] == request
    for name, expected in listed.items():
        path = (root / name).resolve()
        assert path.is_relative_to(root.resolve()), name
        assert path.is_file() and sha(path) == expected, name
    if 'html' in request['formats']:
        html = (root / 'report.html').read_text()
        embedded = re.search(r'<script id="report-provenance" type="application/json">(.*?)</script>', html, re.S)
        assert embedded and json.loads(embedded[1])['request'] == request
        images = Images()
        images.feed(html)
        assert len(images.sources) == len(request['datasets'])
        assert all(src.startswith('data:') for src in images.sources)
    if 'pdf' in request['formats']:
        assert (root / 'report.pdf').read_bytes().startswith(b'%PDF-')
    return root


def main():
    os.chdir(ROOT)
    if OUT.exists():
        raise RuntimeError(f'Use a clean checkout for the image test; {OUT} already exists')
    OUT.mkdir(parents=True)
    if platform.system() != 'Linux' or platform.machine() != 'x86_64':
        raise RuntimeError('This test targets the Linux x86_64 image')
    assert platform.python_version() == '3.11.6'
    configured_library = os.environ.get('HEALTH_REPORT_R_LIBRARY')
    assert configured_library == '/opt/health-report-r-library'
    environment = {'python': platform.python_version(), 'image_tag': os.environ.get('REQUEST_IMAGE')}
    for name, command in {
        'snakemake': [sys.executable, '-m', 'snakemake', '--version'],
        'quarto': ['quarto', '--version'],
        'r': ['Rscript', '-e', 'cat(R.version.string)'],
        'tex': ['xelatex', '--version'],
    }.items():
        environment[name], _ = run(command)
    assert environment['snakemake'].strip() == '8.30.0'
    assert environment['quarto'].strip() == '1.3.353'
    run(['Rscript', '-e', 'stopifnot(as.character(getRversion()) == "4.3.2"); '
         'stopifnot(normalizePath(.libPaths()[1]) == normalizePath(Sys.getenv("HEALTH_REPORT_R_LIBRARY"))); '
         'for (p in c("ggplot2", "knitr", "rmarkdown", "jsonlite")) '
         'stopifnot(startsWith(find.package(p), Sys.getenv("HEALTH_REPORT_R_LIBRARY")))'])
    # Confirm every restored R package matches the repository lock.
    run(['Rscript', '-e', 'lock <- jsonlite::fromJSON("renv.lock", simplifyVector=FALSE); '
         'for (p in names(lock$Packages)) '
         'stopifnot(packageDescription(p, fields="Version") == lock$Packages[[p]]$Version)'])
    timings = {}
    _, timings['regression_tests_seconds'] = run([sys.executable, '-m', 'pytest', '-q'])
    request = json.loads((ROOT / 'examples/requests/public-health.json').read_text())
    request.update(request_id='image-public-health', audience='public_health_expert', formats=['html'])
    path = OUT / 'request.json'
    path.write_text(json.dumps(request))
    command = [sys.executable, '-m', 'snakemake', '--cores', '2', '--config',
               f'request_file={path}', f'out={OUT}']
    _, timings['first_html_seconds'] = run(command)
    matches = list((OUT / 'requests').glob('image-public-health-*/result.json'))
    assert len(matches) == 1
    first = verify_result(matches[0], request)
    assert not (first / 'report.pdf').exists(), 'HTML-only request unexpectedly created a PDF'
    seals = {str(p): (sha(p), p.stat().st_mtime_ns) for p in (OUT / 'cache/prepared').glob('*/prepared.json')}
    assert len(seals) == 1
    request.update(request_id='image-researcher', audience='researcher', formats=['html', 'pdf'])
    path.write_text(json.dumps(request))
    _, timings['second_audience_html_pdf_seconds'] = run(command)
    matches = list((OUT / 'requests').glob('image-researcher-*/result.json'))
    assert len(matches) == 1
    second = verify_result(matches[0], request)
    assert sha(first / 'data/series.csv') == sha(second / 'data/series.csv')
    current_seals = {str(p): (sha(p), p.stat().st_mtime_ns) for p in (OUT / 'cache/prepared').glob('*/prepared.json')}
    assert current_seals == seals, 'Audience-only change unnecessarily repeated preparation'
    dry_run, timings['unchanged_dry_run_seconds'] = run(command[:3] + ['--dry-run'] + command[3:])
    assert 'Nothing to be done' in dry_run
    evidence = {'status': 'success', 'environment': environment, 'timings': timings,
                'prepared_data_reused': True, 'audience_values_identical': True,
                'requests': [str(first.relative_to(OUT)), str(second.relative_to(OUT))]}
    (OUT / 'image-test.json').write_text(json.dumps(evidence, indent=2))
    print('Image tests passed: HTML, PDF, provenance, artifact hashes, preparation reuse and unchanged rerun.')


if __name__ == '__main__':
    main()
