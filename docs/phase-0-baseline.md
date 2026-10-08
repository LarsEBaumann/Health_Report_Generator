# Phase 0 baseline — 2026-10-08

This document records the repository baseline before any cleanup, renaming, data migration, deduplication, or deletion.

## Source state

- Repository: `LarsEBaumann/Health_Report_Generator`
- Baseline branch: `chore/phase-0-baseline`
- Baseline commit: `4ce483491ac7891ed04acc2b1f89917f93af3880`
- Baseline commit message: `Update IDD reference data`
- Tracked files: 325
- Working tree after checkout: clean

## Commands executed

```sh
python -m pip install -r scripts/health_pipeline/requirements.lock.txt
python -m pytest -q
snakemake --dry-run --cores 1 --config data_root=Data
snakemake --cores 2 --config data_root=Data --printshellcmds
snakemake tables --cores 2 --config out=baseline_reference
```

The local inspection environment provided Python 3.12.8 but did not provide R, Quarto, TinyTeX, or Docker. Therefore the complete HTML/PDF/Shiny build could not be validated locally; CI remains the authoritative complete-build environment for this baseline.

## Test and workflow results

- Python tests: **PASS**, 44 tests passed in 3.92 seconds.
- Snakemake dry run with `data_root=Data`: **PASS**, 9 jobs planned.
- Pipeline through inventory, harmonisation, validation, and analysis with `data_root=Data`: **PASS**.
- Complete local build: **BLOCKED BY ENVIRONMENT**, because the `quarto` executable was unavailable when HTML and PDF rendering began; this was not a scientific validation failure.
- Default lowercase `data/reference` tables target: **PASS**.

## Uppercase `Data/` baseline

- Snapshot ID: `f1484622df74831453d66fb36cfc9fab002bd0695385195143930328d4f74653`
- Snapshot files: 74
- Dataset records: 37
- Quality checks: 370 total; 347 PASS, 21 SKIP, 2 WARN, 0 FAIL
- Selection: 20 candidate series; 12 included and 8 excluded
- Analysis outputs: 72 `series.csv` rows and 296 `metrics.csv` rows
- Bundle hashes were generated successfully for the analysis tables.

The two warnings concern missing values in wastewater datasets: one series is 100% missing and another is 52.7% missing. Report selection requires complete values, so the warnings do not silently enter the selected report series.

## Duplicate and path inventory

The uppercase `Data/` tree contains 37 dataset directories but only 20 unique data-plus-metadata byte pairs. There are 9 exact duplicate groups containing 17 redundant directory copies. No same-data/different-metadata conflict was found in this byte-level inventory.

Two dataset directories are unexpectedly nested inside `Data/RESPVIRUSES_wastewater (1)/`:

- `RESPVIRUSES_wastewater (3)`
- `SHIGELLOSIS_oblig`

No duplicate directory or nested directory has been deleted. Any future migration must preserve the recorded snapshot and compare post-migration analysis-table hashes or independently documented expected changes.

## Lowercase `data/reference` baseline

- Snapshot ID: `d0709708a8057815801497701bfaa145017979f1ecace4508ae46237438573ee`
- Snapshot files: 168
- Dataset records: 56
- Quality checks: 853 total; 774 PASS, 76 SKIP, 3 WARN, 0 FAIL
- Selection: 56 candidate series; 12 included and 44 excluded
- Analysis outputs: 72 `series.csv` rows and 296 `metrics.csv` rows

The two roots produce different snapshots and inventories, but the currently selected stakeholder analysis produced the same row counts for `series.csv` and `metrics.csv`. Row-count equality is not proof of content equality; later migration work must compare content hashes and metric values before choosing the canonical root.

## Environment divergence

- README, Conda configuration, and GitHub Actions describe Python 3.11/3.11.6.
- `pyproject.toml` requires Python 3.14 or newer.
- Docker uses Python 3.14.
- README, Conda configuration, and GitHub Actions use Quarto 1.3.353.
- Docker uses Quarto 1.9.38.

These differences must be resolved before the environment is treated as a single reproducible contract.

## Repository hygiene observations

- Two tracked `.DS_Store` files are present under `scripts/health_pipeline/`.
- The default pipeline configuration points to lowercase `data/reference`; the main validation workflow overrides the root to uppercase `Data`.
- Three presentation profiles exist, but the main Snakemake configuration enables one stakeholder file.

## Baseline gate

No destructive cleanup is approved by this record. Before deleting or moving data, the next phase must:

1. Preserve this commit and both snapshot IDs.
2. Produce a machine-readable duplicate-resolution map.
3. Compare pre/post-migration table contents and hashes, not only row counts.
4. Explain every intentional difference.
5. Keep validation at zero FAIL results.
