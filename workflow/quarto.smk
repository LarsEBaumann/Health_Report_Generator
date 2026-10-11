# Quarto reports built from reports/*.qmd.
#
# The reports are generated, never maintained as HTML: the .qmd documents and the shared
# reports/shared/helpers.py are the only source, and the HTML under results/site is a build
# artifact. Included by the Snakefile, which defines OUT, P, PYTHON, QUARTO, DATA_ROOT
# and ENVIRONMENT.

import shutil

QUARTO_REPORTS = list(config.get('quarto_reports') or [])
SITE = OUT + '/site'
QUARTO_CODE = ['reports/shared/helpers.py', 'reports/shared/provenance.py',
               'reports/assets/swiss_cantons.geojson', f'{P}/render_quarto.py']

for name in QUARTO_REPORTS:
    if not Path(f'reports/{name}.qmd').exists():
        raise ValueError(f'quarto_reports lists {name}, but reports/{name}.qmd does not exist')

QUARTO_HTML = expand(SITE + '/{report}.html', report=QUARTO_REPORTS)
QUARTO_PROVENANCE = expand(SITE + '/provenance_{report}.json', report=QUARTO_REPORTS)
QUARTO_SITE = (QUARTO_HTML + QUARTO_PROVENANCE + [SITE + '/index.html']) if QUARTO_REPORTS else []

if QUARTO_REPORTS:

    rule quarto:
        input: QUARTO_SITE

    # The reports read the cleaned table as CSV and publish its checksum in their
    # Provenance section; harmonise.py writes Parquet, so the CSV is derived here.
    rule harmonised_csv:
        input:
            parquet=OUT + '/harmonised.parquet', gate=OUT + '/validated.json',
            code=[f'{P}/export_csv.py', f'{P}/common.py'], env=ENVIRONMENT
        output: OUT + '/harmonised.csv'
        params: out=OUT
        shell: '{PYTHON:q} {P}/export_csv.py --out {params.out:q}'

    rule quarto_report:
        # Everything helpers.py and provenance.py read; the gate stops a report from
        # being built on a table that has not passed checks.py.
        input:
            cleaned=OUT + '/harmonised.csv', snapshot=OUT + '/harmonised_snapshot.json',
            datasets=OUT + '/datasets.csv', checks=OUT + '/checks.csv', gate=OUT + '/validated.json',
            qmd='reports/{report}.qmd', code=QUARTO_CODE, env=ENVIRONMENT
        output: html=SITE + '/{report}.html', provenance=SITE + '/provenance_{report}.json'
        wildcard_constraints: report='|'.join(QUARTO_REPORTS)
        params: results=OUT, data_root=DATA_ROOT or config.get('snapshot_manifest')
        shell:
            '{PYTHON:q} {P}/render_quarto.py --report {wildcards.report:q} '
            '--results {params.results:q} --output {output.html:q} --quarto {QUARTO:q} '
            '--data-root {params.data_root:q}'

    # The landing page links to the reports by file name, so it is only published once
    # every report it links to exists.
    rule quarto_landing:
        input: page='reports/assets/index.html', reports=QUARTO_HTML
        output: SITE + '/index.html'
        run:
            Path(output[0]).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(input.page, output[0])
