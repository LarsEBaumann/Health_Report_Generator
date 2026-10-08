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

Outputs for the default stakeholder:

- `results/reports/public_health_expert/report.html`
- `results/reports/public_health_expert/report.pdf`
- `results/reports/public_health_expert/data/`: CSVs, configuration and integrity manifest
- `results/reports/public_health_expert/app/`: portable QMD, Shiny app and the same data
- `results/release.json`: artifact hashes, code hashes, Git state and actual environment versions
- `results/snapshots/<snapshot_id>/`: archived original CSVs and metadata

Launch Shiny from the repository root:

```sh
Rscript -e 'shiny::runApp("results/reports/public_health_expert/app")'
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

Copy a stakeholder JSON, set a unique `id`, and add the filename stem to `workflow/config.yaml`. Filename stem and ID must match. Only supported settings pass `workflow/config.schema.json`; unsupported geographies, periods, classes, sections, and unknown keys fail clearly. Change presentation sections with `outputs`. Arbitrary new analyses require code plus tests, not an ignored configuration field.

See [SCHEMA.md](scripts/health_pipeline/SCHEMA.md) for table keys, types and calculation lineage. `pathogen_class.csv` remains a curated lookup: review classifications and the note column before adding topics. Unclassified datasets are explicitly excluded, never relabelled as syndromic. The current classifications were supplied by the team; no scientific reviewer approval is invented.

## Tests and release discipline

```sh
python -m pytest -q
Rscript tests/shiny_smoke.R results/reports/public_health_expert/app
snakemake --dry-run --cores 1
```

Tests cover subgroup safety, incomplete months/years/baselines, denominators, source completeness, metadata conflicts, overlapping exports, nonzero CLI failures, stale gates, snapshot relocation/tampering, deterministic tables, and independent reconstruction of every fixture metric from raw records and formula inputs. The final dry run should say no work is needed after a successful unchanged build.

CI runs tests, builds all outputs, checks Shiny server outputs, and uploads a release bundle only after success. It does not deploy or overwrite a production site. A failed local build may leave older reports on disk; treat only a successfully completed build and its matching `release.json` as a release. Preserve previously uploaded successful artifacts independently of a new build.

The production Python lock at `scripts/health_pipeline/requirements.lock.txt` pins the Snakemake/report pipeline; `uv.lock` pins the optional Marimo/connector environment from `pyproject.toml`; `renv.lock` records R dependencies. `workflow/toolchain.json` is the machine-readable source of runtime version policy. `workflow/environment.yml` is an alternative convenience environment, not an additional authoritative lock.

See [GETTING_STARTED.md](GETTING_STARTED.md) for setup and reproduction instructions.
