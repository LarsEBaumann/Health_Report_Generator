# Repository map

This map distinguishes the supported production workflow from optional, experimental, and historical material. It documents the current repository without changing runtime behavior.

## Production path

| Path | Role | Status |
|---|---|---|
| `Snakefile` | Orchestrates snapshotting, harmonisation, validation, analysis, rendering, packaging, and release metadata. | Active |
| `workflow/config.yaml` | Selects the data root, output root, renderer, stakeholder list, and optional archived snapshot. | Active |
| `workflow/config.schema.json` | Validates stakeholder configuration. | Active |
| `scripts/health_pipeline/` | Core Python pipeline, report source, R helpers, and configuration. | Active, pending package consolidation |
| `scripts/health_pipeline/config/stakeholders/` | Scientific and reporting parameters for the default stakeholder build. | Active |
| `scripts/health_pipeline/templates/` | Shared presentation helpers, methods report, Shiny app, and styles. | Active |
| `tests/` | Python pipeline tests and R rendering/application smoke tests. | Active |
| `.github/workflows/validate.yml` | Full test and report build in CI. | Active |
| `.github/workflows/update-lyme-data.yml` | Scheduled/manual IDD synchronization and versioned artifact build. | Active |

## Optional interfaces

| Path | Role | Status |
|---|---|---|
| `src/ui.py` | Marimo interface that dispatches selected audience/dataset reports through GitHub Actions. | Optional interface |
| `src/artifact_download.py` | Downloads the versioned source artifact used by the Marimo interface. | Optional interface |
| `.github/workflows/render-selected-report.yml` | Renders a selected report from an exact lineage artifact. | Optional but supported |
| `src/fetch_idd.py`, `src/sync_idd_exports.py`, `src/update_idd_reference.py` | IDD acquisition and synchronization utilities. | Active connector utilities |
| `Dockerfile`, `compose.yaml` | Container environment for the Marimo/connector path. | Experimental until versions are aligned with CI |

## Historical material

| Path | Role | Status |
|---|---|---|
| `scripts/health_pipeline/example_output/` | Outputs from an earlier prototype. | Historical; not release evidence |
| `Health_Report_Generator-test/quarto/` | Standalone audience-report prototype with committed rendered files. | Historical prototype; not part of Snakemake |
| `design/report-mockups.html` | Alternate editorial design exploration. | Historical design reference |
| `configs/report.yml` | Small dataset-selection configuration from an earlier path. | Legacy; not consumed by the main Snakefile |

Historical material must not be cited as proof that the current workflow built successfully. Supported release evidence is a successful current workflow run and its matching `results/release.json`.

## Current ambiguity

The default local configuration reads `data/reference`, while the validation workflow explicitly reads `Data`. Their inventories and snapshot IDs differ. No canonical-root migration is performed in Phase 1; see `docs/phase-0-baseline.md` and `data/README.md` for the safety gate.
