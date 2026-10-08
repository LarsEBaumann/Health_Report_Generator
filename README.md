# Reproducible infectious-disease reports

This workflow archives a local data release, validates it, calculates stakeholder metrics once, and produces a Quarto HTML report, PDF report, and R Shiny application using the same CSV tables.

```text
data/reference/ -> snapshot + hashes -> harmonised.parquet -> blocking quality checks
  -> stakeholder analysis -> report CSVs + lineage -> Quarto HTML / PDF + Shiny bundle
```

## Setup and run

Run commands from the repository root. The supported and validated toolchain is recorded in `workflow/toolchain.json`: Python 3.11.6 (supported range `>=3.11.6,<3.12`), R 4.3.2, Quarto 1.3.353, and uv 0.8.14. CI, Conda metadata, Docker, and project metadata are checked against this contract.

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r scripts/health_pipeline/requirements.lock.txt
Rscript workflow/restore_r.R
```

Install Quarto **1.3.353**. CI installs the checksum-pinned full **TinyTeX v2026.10** bundle through `scripts/ci/install_tinytex.sh`; local PDF builds require an equivalent TeX installation. The installer verifies the archive digest and the required KOMA-Script class before rendering. Place `quarto` on PATH, or supply its path below. These are explicit installation steps; ordinary builds never fetch new data or install packages deliberately. Quarto's automatic TeX package installation is disabled in the template so PDF builds fail clearly if their TeX environment is incomplete.

```sh
snakemake --cores 2
# On this Mac, when Quarto is bundled with RStudio:
snakemake --cores 2 --config quarto=/Applications/RStudio.app/Contents/Resources/app/quarto/bin/quarto
```

Optional targets: `snakemake tables --cores 1`, `snakemake html --cores 1`, `snakemake pdf --cores 1`, `snakemake shiny --cores 1`.

`bash scripts/health_pipeline/run_all.sh data/reference results` is a compatibility wrapper around Snakemake. Set `QUARTO` to override the renderer path. The former Python-generated HTML is replaced by the shared QMD to avoid duplicate statistical logic.

## Three audiences from one source

The single command `snakemake --cores 2` renders one shared Quarto source (`scripts/health_pipeline/report_public_health_expert.qmd`, a generic template despite its historical filename) once per stakeholder listed in `workflow/config.yaml`. Audiences differ only through their parameter files in `scripts/health_pipeline/config/stakeholders/`; no template is copied per audience.

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

## Reproduce a specific archived release

```sh
snakemake --cores 2 --config \
  snapshot_manifest=results/snapshots/REPLACE_WITH_SNAPSHOT_ID/manifest.json \
  out=reproduced
```

This mode verifies and reads only that archived snapshot, without requiring the live `data/reference/` tree or any API. Retain the snapshot **and** code/config/environment versions with the report. Hashes cannot recover deleted data. Paths inside a snapshot and its lineage are relative, so the archive can move between computers. Original source record numbers count CSV records (header = 1), not physical lines in multiline CSV fields.

For an update, place a new release in `data/reference/` and run the ordinary workflow. It creates a new content-addressed archive rather than replacing the old snapshot. Remote API acquisition is deliberately separate: no endpoint, authentication, or download specification was supplied. The included weekly CI job rebuilds the committed data; it does **not** claim to fetch newer surveillance data.

## Scientific and quality policy

- A subgroup is never inferred to be a total because it has one distinct value.
- Missing/malformed metadata and undescribed columns are quarantined; quarantine blocks the release until resolved.
- Deduplication requires identical data **and metadata** bytes. Same data with conflicting metadata is a blocking conflict.
- Counts must be numeric, finite, nonnegative and uniquely keyed. Year/month reconciliation uses a documented 2% tolerance only for complete compatible count series. Canton checks require exactly 26 Swiss cantons and a **CH** national total, never CHFL; tolerance is 5%. Nonapplicable checks are `SKIP`, not `PASS`.
- Every selected series requires the reference year, index base year, and every requested reporting year, confirmed `dataComplete`, and a positive population denominator. An annual total is preferred; otherwise exactly 12 distinct months and one consistent denominator are required.
- Duplicate candidate exports for the same disease/source are rejected, not summed. Different systems follow the explicit `source_priority`; every choice is recorded.
- Geography is explicit (`CH` or `CHFL`); the workflow never silently substitutes one for the other.
- Group membership is fixed across all displayed years. Groups sum mandatory case notifications only by default, excluding sentinel estimates. COVID-19 and AIDS are excluded from group sums; AIDS is a disease stage related to HIV. Influenza exclusion is a separate sensitivity comparison. These are editable, documented analytic policies, not hidden harmonisation rules.
- The COVID-19 positive-test case definition is an explicit, reasoned dimension filter. COVID-19 still lacks a 2019 baseline, so it is excluded from this default complete-baseline comparison. To study it, use an appropriate later reference period rather than substituting zero.
- Rates are calculated from the exported counts and population, and can differ slightly from a publisher's rate calculated using unrounded figures. Relative changes are descriptive, not significance tests or causal claims.
- `checks.py` exits nonzero on critical failures. Analysis verifies a content-bound success marker; rendering verifies the analysis bundle. Editing an input or output cannot silently reuse an old validation result.

The strict defaults may exclude more series than the previous prototype. Inspect `selection.csv` before interpreting a report. The default input release produces 12 eligible disease series; CH-only sentinel series and COVID-19 without a 2019 baseline are among the exclusions.

## Stakeholders and data contract

Copy a stakeholder JSON, set a unique `id`, and add the filename stem to `workflow/config.yaml`. Filename stem and ID must match. `public_health_expert.json` is retained as the analytic base profile for the on-demand selected-report workflow (`render_selected.py`); it is no longer part of the default build. Only supported settings pass `workflow/config.schema.json`; unsupported geographies, periods, classes, sections, and unknown keys fail clearly. Change presentation sections with `outputs`. Arbitrary new analyses require code plus tests, not an ignored configuration field.

See [SCHEMA.md](scripts/health_pipeline/SCHEMA.md) for table keys, types and calculation lineage. `pathogen_class.csv` remains a curated lookup: review classifications and the note column before adding topics. Unclassified datasets are explicitly excluded, never relabelled as syndromic. The current classifications were supplied by the team; no scientific reviewer approval is invented.

## Tests and release discipline

```sh
python -m pytest -q
Rscript tests/shiny_smoke.R results/reports/researcher/app
snakemake --dry-run --cores 1
```

Tests cover subgroup safety, incomplete months/years/baselines, denominators, source completeness, metadata conflicts, overlapping exports, nonzero CLI failures, stale gates, snapshot relocation/tampering, deterministic tables, and independent reconstruction of every fixture metric from raw records and formula inputs. The final dry run should say no work is needed after a successful unchanged build.

CI runs tests, builds all outputs, checks Shiny server outputs, and uploads a release bundle only after success. It does not deploy or overwrite a production site. A failed local build may leave older reports on disk; treat only a successfully completed build and its matching `release.json` as a release. Preserve previously uploaded successful artifacts independently of a new build.

The production Python lock at `scripts/health_pipeline/requirements.lock.txt` pins the Snakemake/report pipeline; `uv.lock` pins the optional Marimo/connector environment from `pyproject.toml`; `renv.lock` records R dependencies. `workflow/toolchain.json` is the machine-readable source of runtime version policy. `workflow/environment.yml` is an alternative convenience environment, not an additional authoritative lock.

See [GETTING_STARTED.md](GETTING_STARTED.md) for setup and reproduction instructions.
