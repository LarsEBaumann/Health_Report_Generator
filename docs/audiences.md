# Audiences, outputs and provenance

One shared Quarto source is rendered once per audience. This document is the full reference; the README has the summary.

The single command `snakemake --cores 2` (or `bash scripts/health_pipeline/run_all.sh`) renders one shared Quarto source (`scripts/health_pipeline/report_public_health_expert.qmd`, a generic template despite its historical filename) once per stakeholder listed in `workflow/config.yaml`. Audiences differ only through their parameter files in `scripts/health_pipeline/config/stakeholders/`; no template is copied per audience.

| Stakeholder id | Audience | Presentation (`layout` / `detail_level`) | What it emphasises |
|---|---|---|---|
| `researcher` | Researchers, epidemiologists | `technical` / `full` | Effective parameters and filters, selected data coverage, quality-check counts, methods, all disease-level results, metric identifiers and reproduction code |
| `health_institution` | Health offices and monitoring staff | `dashboard` / `monitoring` | Headline changes, a monitoring summary ranked by absolute case differences with a small-number flag, group trends, quality summary |
| `public` | Broad public | `editorial` / `plain_language` | Plain-language findings, a prominent “How sure can we be?” section translating uncertainty, and a readable provenance block |

All three share identical analytic parameters (geography, years, reference year, exclusions, source priority), so their numbers agree; `tests/test_audiences.py` enforces this. Uncertainty and limitations are shown to every audience; for non-technical audiences they are translated, not removed. The operational scope is the national Switzerland + Liechtenstein (`CHFL`) total: the schema supports only `CH`/`CHFL`, canton-level series are not available for every selected disease, and a `CH`-only scope would drop influenza for lack of a complete 2019 baseline (see `docs/phase-5-multi-audience-reports.md`).

Outputs per stakeholder `<id>` (`researcher`, `health_institution`, `public`):

- `results/reports/<id>/report.html` and `methods.html`: interactive HTML (filterable, sortable tables; contents navigation; expandable details)
- `results/reports/<id>/report.pdf` and `methods.pdf`
- `results/reports/<id>/provenance.json` (HTML) and `provenance.pdf.json` (PDF): machine-readable provenance
- `results/reports/<id>/data/`: CSVs, effective `stakeholder.json` and integrity manifest
- `results/reports/<id>/app/`: portable QMD, Shiny app and the same data
- `results/release.json`: artifact hashes, code hashes, Git state and actual environment versions
- `results/snapshots/<snapshot_id>/`: archived original CSVs, metadata and API retrieval records

Check a completed build with `python scripts/health_pipeline/check_outputs.py` (CI runs it): it confirms exactly one HTML report per configured audience, embedded and sidecar provenance, interactive tables, and distinct presentations.

To add an audience, copy a stakeholder JSON, set a unique `id` (matching the filename), adjust `title`, `question`, `outputs` and `presentation`, and add the id to `workflow/config.yaml`. No template change is needed.

### Provenance format

Every HTML page embeds its record as `<script type="application/json" id="report-provenance">`, identical to the `provenance.json` sidecar (schema `health-report-provenance/1.0`). It records: render timestamp (UTC); output format and the shared template hash; stakeholder id, presentation and the full effective parameters; applied filters (geography, years, reference/index years, measures, exclusions, sensitivity exclusion, source priority, dimension filters); data publisher, API pattern, canonical root (`data/reference`) or snapshot manifest, snapshot id, publisher release-date range, API retrieval-date range and per-dataset source URLs and hashes; analysis-bundle file hashes; quality-check counts; Python, key package, Quarto and R versions plus hashes of `workflow/toolchain.json`, `renv.lock` and the Python lock; and the Git commit with a clean/dirty flag. Read it with:

```sh
python -c "import json;print(json.load(open('results/reports/public/provenance.json'))['data']['snapshot_id'])"
```

Launch Shiny from the repository root:

```sh
Rscript -e 'shiny::runApp("results/reports/researcher/app")'
```

The portable app folder also contains `report.qmd`. From that folder, `quarto render report.qmd --to html` or `--to pdf` renders the same analysis. Shiny is a running R application; it is not a third static export of the PDF/HTML template. Sharing the folder does not deploy a public service.
