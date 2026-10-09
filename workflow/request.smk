from pathlib import Path
import json
import sys

P = 'scripts/health_pipeline'
sys.path.insert(0, str(Path(P).resolve()))
from common import digest, object_hash, write_json
from inventory import verify
from request_pipeline import read_request, preparation_key, verify_prepared, BUNDLE_FILES, PREP_FILES

OUT = config['out'].rstrip('/')
PYTHON = sys.executable
QUARTO = config.get('quarto', 'quarto')
REQUEST_FILE = config['request_file']
REQUEST = read_request(REQUEST_FILE)
REQUEST_HASH = object_hash(REQUEST)
DEST = f"{OUT}/requests/{REQUEST['request_id']}-{REQUEST_HASH[:12]}"
FORMATS = REQUEST['formats']
REPORTS = [f'{DEST}/report.{f}' for f in FORMATS]
PROVENANCE = [f'{DEST}/report.{f}.provenance.json' for f in FORMATS]
BUNDLE = [f'{DEST}/data/{n}' for n in BUNDLE_FILES + ['bundle.json']]
ENVIRONMENT = [f'{P}/requirements.lock.txt', 'workflow/environment.yml', 'renv.lock', '.Rprofile']

rule all:
    input: DEST + '/result.json'

if config.get('snapshot_manifest'):
    SNAPSHOT = config['snapshot_manifest']
    ARCHIVE_ROOT, MANIFEST = verify(SNAPSHOT)
    SID = MANIFEST['snapshot_id']
    ARCHIVED = [str(ARCHIVE_ROOT / f['path']) for f in MANIFEST['files']]
else:
    ROOT = Path(config['data_root'])
    RAW = sorted({str(p) for csv in ROOT.rglob('data.csv') for p in [csv, *csv.parent.glob('*.json')]})
    if not RAW:
        raise ValueError('No data.csv files found; set data_root or snapshot_manifest')
    ENTRIES = [{'path': Path(p).relative_to(ROOT).as_posix(), 'sha256': digest(p), 'bytes': Path(p).stat().st_size} for p in RAW]
    SID = object_hash(ENTRIES)
    SNAPSHOT = f'{OUT}/snapshots/{SID}/manifest.json'
    ARCHIVED = [f'{OUT}/snapshots/{SID}/' + e['path'] for e in ENTRIES]
    if Path(SNAPSHOT).exists():
        verify(SNAPSHOT)
    rule request_inventory:
        input: raw=RAW, code=[f'{P}/inventory.py', f'{P}/common.py']
        output: manifest=SNAPSHOT, archived=ARCHIVED
        params: root=str(ROOT), out=OUT
        shell: '{PYTHON:q} {P}/inventory.py {params.root:q} --out {params.out:q}'

PREPARED = f'{OUT}/cache/prepared/{preparation_key(SID)}'
if Path(PREPARED + '/prepared.json').exists():
    verify_prepared(PREPARED)

rule request_prepare:
    input: snapshot=SNAPSHOT, archived=ARCHIVED,
           code=[f'{P}/harmonise.py', f'{P}/inventory.py', f'{P}/common.py', f'{P}/request_pipeline.py'], env=ENVIRONMENT
    output: [f'{PREPARED}/{n}' for n in PREP_FILES + ['prepared.json']]
    params: out=PREPARED
    shell:
        '{PYTHON:q} {P}/harmonise.py --snapshot {input.snapshot:q} --out {params.out:q} && '
        '{PYTHON:q} {P}/request_pipeline.py seal --prepared {params.out:q}'

rule request_analyse:
    input: prepared=[f'{PREPARED}/{n}' for n in PREP_FILES + ['prepared.json']], snapshot=SNAPSHOT,
           request=REQUEST_FILE, code=[f'{P}/request_pipeline.py', f'{P}/checks.py', f'{P}/common.py', 'workflow/request.schema.json']
    output: BUNDLE
    params: prepared=PREPARED, dest=DEST + '/data'
    shell: '{PYTHON:q} {P}/request_pipeline.py analyse --prepared {params.prepared:q} --request {input.request:q} --snapshot {input.snapshot:q} --dest {params.dest:q}'

rule request_render:
    input: bundle=BUNDLE, code=[f'{P}/request_pipeline.py', f'{P}/templates/request_report.qmd', f'{P}/common.py'], env=ENVIRONMENT
    output: report=DEST + '/report.{fmt}', provenance=DEST + '/report.{fmt}.provenance.json'
    wildcard_constraints: fmt='html|pdf'
    params: bundle=DEST + '/data'
    shell: '{PYTHON:q} {P}/request_pipeline.py render --bundle {params.bundle:q} --format {wildcards.fmt:q} --output {output.report:q} --quarto {QUARTO:q}'

rule request_release:
    input: REPORTS, PROVENANCE, BUNDLE, f'{P}/request_pipeline.py'
    output: DEST + '/result.json'
    params: dest=DEST, formats=FORMATS
    shell: '{PYTHON:q} {P}/request_pipeline.py release --dest {params.dest:q} --formats {params.formats:q}'

onerror:
    Path(DEST + '/result.json').unlink(missing_ok=True)
    write_json(Path(DEST) / 'failure.json', {'status': 'failed', 'request_id': REQUEST['request_id'], 'detail': 'See Snakemake log for the failing rule.'})

onsuccess:
    Path(DEST + '/failure.json').unlink(missing_ok=True)
