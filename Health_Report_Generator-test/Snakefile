from pathlib import Path
import json
import sys

configfile: 'workflow/config.yaml'
P = 'scripts/health_pipeline'
sys.path.insert(0, str(Path(P).resolve()))
from common import digest, object_hash
OUT = config['out'].rstrip('/')
STAKEHOLDERS = config['stakeholders']
PYTHON = sys.executable
QUARTO = config.get('quarto', 'quarto')
for s in STAKEHOLDERS:
    if json.loads(Path(f'{P}/config/stakeholders/{s}.json').read_text())['id'] != s:
        raise ValueError('Stakeholder filename and id must match')
CONFIGS = {s: f'{P}/config/stakeholders/{s}.json' for s in STAKEHOLDERS}
BUNDLE_NAMES = ['series.csv','metrics.csv','lineage.csv','selection.csv','sources.csv','checks.csv',
                'snapshot.json','stakeholder.json','pathogen_class.csv','bundle.json']
ANALYSIS = expand(OUT+'/reports/{s}/data/{n}',s=STAKEHOLDERS,n=BUNDLE_NAMES)
HTML = expand(OUT+'/reports/{s}/report.html',s=STAKEHOLDERS)
PDF = expand(OUT+'/reports/{s}/report.pdf',s=STAKEHOLDERS)
APPS = expand(OUT+'/reports/{s}/app/package.json',s=STAKEHOLDERS)
ENVIRONMENT = [f'{P}/requirements.lock.txt', 'workflow/environment.yml', 'workflow/r-packages.tsv', 'renv.lock', '.Rprofile']

rule all:
    input: HTML, PDF, APPS, OUT+'/release.json'

rule tables:
    input: ANALYSIS

rule html:
    input: HTML

rule pdf:
    input: PDF

rule shiny:
    input: APPS

if not config.get('snapshot_manifest'):
    ROOT = Path(config['data_root'])
    RAW = sorted({str(p) for csv in ROOT.rglob('data.csv') for p in [csv,*csv.parent.glob('*.json')]})
    if not RAW:
        raise ValueError(f'No raw datasets in {ROOT}; set data_root or snapshot_manifest')
    ENTRIES = [{'path':Path(p).relative_to(ROOT).as_posix(),'sha256':digest(p),'bytes':Path(p).stat().st_size} for p in RAW]
    SID = object_hash(ENTRIES)
    ARCHIVED = [f'{OUT}/snapshots/{SID}/'+e['path'] for e in ENTRIES]
    SNAPSHOT = OUT+'/snapshot.json'
    rule inventory:
        input: raw=RAW, code=[f'{P}/inventory.py',f'{P}/common.py']
        output: manifest=SNAPSHOT, archived=ARCHIVED, archive_manifest=f'{OUT}/snapshots/{SID}/manifest.json'
        params: root=str(ROOT), out=OUT
        shell: '{PYTHON:q} {P}/inventory.py {params.root:q} --out {params.out:q}'
else:
    SNAPSHOT = config['snapshot_manifest']
    from inventory import verify
    ARCHIVE_ROOT, MANIFEST = verify(SNAPSHOT)
    ARCHIVED = [str(ARCHIVE_ROOT/f['path']) for f in MANIFEST['files']]

rule harmonise:
    input: snapshot=SNAPSHOT, archive=ARCHIVED, code=[f'{P}/harmonise.py',f'{P}/common.py',f'{P}/inventory.py'], env=ENVIRONMENT
    output: parquet=OUT+'/harmonised.parquet', datasets=OUT+'/datasets.csv', roles=OUT+'/role_log.csv', manifest=OUT+'/harmonised_snapshot.json'
    params: out=OUT
    shell: '{PYTHON:q} {P}/harmonise.py --snapshot {input.snapshot:q} --out {params.out:q}'

rule validate:
    input: parquet=OUT+'/harmonised.parquet', datasets=OUT+'/datasets.csv', manifest=OUT+'/harmonised_snapshot.json', code=[f'{P}/checks.py',f'{P}/common.py'], env=ENVIRONMENT
    output: checks=OUT+'/checks.csv', gate=OUT+'/validated.json'
    params: out=OUT
    shell: '{PYTHON:q} {P}/checks.py --out {params.out:q}'

rule analyse:
    input: parquet=OUT+'/harmonised.parquet', datasets=OUT+'/datasets.csv', manifest=OUT+'/harmonised_snapshot.json', checks=OUT+'/checks.csv',gate=OUT+'/validated.json',
           stakeholder=lambda w:CONFIGS[w.s], classes=f'{P}/config/pathogen_class.csv',code=[f'{P}/analyse.py',f'{P}/common.py','workflow/config.schema.json'], env=ENVIRONMENT
    output: [OUT+'/reports/{s}/data/'+n for n in BUNDLE_NAMES]
    params: out=OUT, dest=lambda w:f'{OUT}/reports/{w.s}/data'
    shell: '{PYTHON:q} {P}/analyse.py --out {params.out:q} --stakeholder {input.stakeholder:q} --classes {input.classes:q} --dest {params.dest:q}'

rule render_html:
    input: bundle=[OUT+'/reports/{s}/data/'+n for n in BUNDLE_NAMES], code=[f'{P}/publish.py',f'{P}/common.py',f'{P}/report_public_health_expert.qmd',f'{P}/templates/report_helpers.R',f'{P}/templates/app.R'], env=ENVIRONMENT
    output: OUT+'/reports/{s}/report.html'
    params: bundle=lambda w:f'{OUT}/reports/{w.s}/data'
    shell: '{PYTHON:q} {P}/publish.py html --bundle {params.bundle:q} --output {output:q} --quarto {QUARTO:q}'

rule render_pdf:
    input: bundle=[OUT+'/reports/{s}/data/'+n for n in BUNDLE_NAMES], code=[f'{P}/publish.py',f'{P}/common.py',f'{P}/report_public_health_expert.qmd',f'{P}/templates/report_helpers.R',f'{P}/templates/app.R'], env=ENVIRONMENT
    output: OUT+'/reports/{s}/report.pdf'
    params: bundle=lambda w:f'{OUT}/reports/{w.s}/data'
    shell: '{PYTHON:q} {P}/publish.py pdf --bundle {params.bundle:q} --output {output:q} --quarto {QUARTO:q}'

rule package_shiny:
    input: bundle=[OUT+'/reports/{s}/data/'+n for n in BUNDLE_NAMES], code=[f'{P}/publish.py',f'{P}/common.py',f'{P}/report_public_health_expert.qmd',f'{P}/templates/report_helpers.R',f'{P}/templates/app.R'], env=ENVIRONMENT
    output: manifest=OUT+'/reports/{s}/app/package.json', files=[OUT+'/reports/{s}/app/'+n for n in BUNDLE_NAMES+['report.qmd','report_helpers.R','app.R']]
    params: bundle=lambda w:f'{OUT}/reports/{w.s}/data',dest=lambda w:f'{OUT}/reports/{w.s}/app'
    shell: '{PYTHON:q} {P}/publish.py package --bundle {params.bundle:q} --output {params.dest:q}'

rule release:
    input: HTML, PDF, APPS, ANALYSIS, ENVIRONMENT, f'{P}/release.py', 'Snakefile', 'workflow/config.yaml', *[str(p) for p in Path('tests').glob('*') if p.is_file()], *[str(p) for p in Path(P).glob('*.py')]
    output: OUT+'/release.json'
    params: out=OUT
    shell: '{PYTHON:q} {P}/release.py --out {params.out:q} --quarto {QUARTO:q}'
