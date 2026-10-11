# Project history

Early development phases, kept for traceability. Phases 5 to 7 remain as separate pages: [phase 5](phase-5-multi-audience-reports.md), [phase 6](phase-6-ci-hardening.md), [phase 7](phase-7-release.md). The data-migration audit records are `phase-3-data-migration.json` and `phase-4-legacy-removal.json`.

---

## Phase 0 baseline — 2026-10-08

This document records the repository baseline before any cleanup, renaming, data migration, deduplication, or deletion.

### Source state

- Repository: `LarsEBaumann/Health_Report_Generator`
- Baseline branch: `chore/phase-0-baseline`
- Baseline commit: `4ce483491ac7891ed04acc2b1f89917f93af3880`
- Baseline commit message: `Update IDD reference data`
- Tracked files: 325
- Working tree after checkout: clean

### Commands executed

```sh
python -m pip install -r scripts/health_pipeline/requirements.lock.txt
python -m pytest -q
snakemake --dry-run --cores 1 --config data_root=Data
snakemake --cores 2 --config data_root=Data --printshellcmds
snakemake tables --cores 2 --config out=baseline_reference
```

The local inspection environment provided Python 3.12.8 but did not provide R, Quarto, TinyTeX, or Docker. Therefore the complete HTML/PDF/Shiny build could not be validated locally; CI remains the authoritative complete-build environment for this baseline.

### Test and workflow results

- Python tests: **PASS**, 44 tests passed in 3.92 seconds.
- Snakemake dry run with `data_root=Data`: **PASS**, 9 jobs planned.
- Pipeline through inventory, harmonisation, validation, and analysis with `data_root=Data`: **PASS**.
- Complete local build: **BLOCKED BY ENVIRONMENT**, because the `quarto` executable was unavailable when HTML and PDF rendering began; this was not a scientific validation failure.
- Default lowercase `data/reference` tables target: **PASS**.

### Uppercase `Data/` baseline

- Snapshot ID: `f1484622df74831453d66fb36cfc9fab002bd0695385195143930328d4f74653`
- Snapshot files: 74
- Dataset records: 37
- Quality checks: 370 total; 347 PASS, 21 SKIP, 2 WARN, 0 FAIL
- Selection: 20 candidate series; 12 included and 8 excluded
- Analysis outputs: 72 `series.csv` rows and 296 `metrics.csv` rows
- Bundle hashes were generated successfully for the analysis tables.

The two warnings concern missing values in wastewater datasets: one series is 100% missing and another is 52.7% missing. Report selection requires complete values, so the warnings do not silently enter the selected report series.

### Duplicate and path inventory

The uppercase `Data/` tree contains 37 dataset directories but only 20 unique data-plus-metadata byte pairs. There are 9 exact duplicate groups containing 17 redundant directory copies. No same-data/different-metadata conflict was found in this byte-level inventory.

Two dataset directories are unexpectedly nested inside `Data/RESPVIRUSES_wastewater (1)/`:

- `RESPVIRUSES_wastewater (3)`
- `SHIGELLOSIS_oblig`

No duplicate directory or nested directory has been deleted. Any future migration must preserve the recorded snapshot and compare post-migration analysis-table hashes or independently documented expected changes.

### Lowercase `data/reference` baseline

- Snapshot ID: `d0709708a8057815801497701bfaa145017979f1ecace4508ae46237438573ee`
- Snapshot files: 168
- Dataset records: 56
- Quality checks: 853 total; 774 PASS, 76 SKIP, 3 WARN, 0 FAIL
- Selection: 56 candidate series; 12 included and 44 excluded
- Analysis outputs: 72 `series.csv` rows and 296 `metrics.csv` rows

The two roots produce different snapshots and inventories, but the currently selected stakeholder analysis produced the same row counts for `series.csv` and `metrics.csv`. Row-count equality is not proof of content equality; later migration work must compare content hashes and metric values before choosing the canonical root.

### Environment divergence

- README, Conda configuration, and GitHub Actions describe Python 3.11/3.11.6.
- `pyproject.toml` requires Python 3.14 or newer.
- Docker uses Python 3.14.
- README, Conda configuration, and GitHub Actions use Quarto 1.3.353.
- Docker uses Quarto 1.9.38.

These differences must be resolved before the environment is treated as a single reproducible contract.

### Repository hygiene observations

- Two tracked `.DS_Store` files are present under `scripts/health_pipeline/`.
- The default pipeline configuration points to lowercase `data/reference`; the main validation workflow overrides the root to uppercase `Data`.
- Three presentation profiles exist, but the main Snakemake configuration enables one stakeholder file.

### Baseline gate

No destructive cleanup is approved by this record. Before deleting or moving data, the next phase must:

1. Preserve this commit and both snapshot IDs.
2. Produce a machine-readable duplicate-resolution map.
3. Compare pre/post-migration table contents and hashes, not only row counts.
4. Explain every intentional difference.
5. Keep validation at zero FAIL results.

---

## Phase 1 safe hygiene

Phase 1 improves repository clarity without changing scientific calculations, source data, workflow configuration, or generated report behavior.

### Included

- Contributor guidance and validation expectations.
- Data-root documentation and a destructive-change safety gate.
- A repository map classifying production, optional, experimental, legacy, and historical paths.
- Explicit notices in historical output/prototype directories.
- Removal of tracked operating-system metadata files.

### Excluded

- No source datasets are moved, renamed, deduplicated, or deleted.
- No environment versions or dependency locks are changed.
- No stakeholder parameters, formulas, selection rules, schemas, or templates are changed.
- No historical prototype is deleted in this phase.

### Acceptance checks

```sh
python -m pytest -q
snakemake --dry-run --cores 1 --config data_root=Data
```

A full CI build remains required before merging.

---

## Phase 2 environment alignment

Phase 2 defines one machine-readable runtime contract and aligns every supported execution path with it.

### Contract

- Python: validated 3.11.6; supported `>=3.11.6,<3.12`
- R: 4.3.2
- Quarto: 1.3.353
- uv: 0.8.14
- TinyTeX: baseline observation 2026.10; actual release version is recorded because CI installation is not byte-locked

The authoritative values are stored in `workflow/toolchain.json`. A regression test checks the Python metadata, Conda metadata, Dockerfile, CI workflows, and setup documentation against this contract.

### Decisions

The existing green full-report CI toolchain is retained as the validated contract. Docker and `pyproject.toml`, which previously required Python 3.14 and Quarto 1.9.38, are aligned to that contract. The optional uv environment remains a separate dependency set from the production Snakemake lock, but both now support the same Python line.

TinyTeX is not described as fully pinned: the setup action installs it dynamically. The workflow records the actual TeX version in release provenance, and the project does not claim byte-identical PDFs across platforms.

### Excluded

- No source data, stakeholder configuration, formulas, selection policy, or templates change.
- No production Python or R package versions change.
- No Quarto upgrade is attempted in this phase.

### Acceptance checks

```sh
python -m pytest -q
uv lock --check
snakemake --dry-run --cores 1 --config data_root=Data
```

A full CI report build and smoke tests are required before merge.

---

## Phase 3 — canonical data root

### Decision

`data/reference/` is the canonical live input root. The default workflow already used it, while CI overrode the default with the older uppercase `Data/` tree. Phase 3 removes that override so local execution and CI read the same source release.

This is not described as deduplication. The roots are not byte-identical: `data/reference/` is broader and newer. The legacy tree is frozen and will be removed only in a separate, reviewable commit after the canonical build is green.

### Pre-migration evidence

The comparison was run from main commit `1aeb1a1414bcbf94ae8acf8288565f5edf21cf71` with the `tables` target against both roots.

| Property | Legacy `Data/` | Canonical `data/reference/` |
|---|---:|---:|
| Snapshot ID | `f1484622df74831453d66fb36cfc9fab002bd0695385195143930328d4f74653` | `d0709708a8057815801497701bfaa145017979f1ecace4508ae46237438573ee` |
| Dataset directories | 37 | 56 |
| Unique data/metadata byte pairs | 20 | 56 |
| Selected report series rows | 72 | 72 |
| Selected report metric rows | 296 | 296 |

The selected topic set and pathogen classification table are unchanged. Scientific table bytes are not identical: 14 series rows differ, including four count rows, twelve population rows, and fourteen calculated incidence rows. Differences are concentrated in revised 2022–2025 counts and 2025 population denominators. The complete hashes and path-level dispositions are in `docs/phase-3-data-migration.json`.

### Safety interpretation

Equal row counts do not establish data equivalence. The canonical root is accepted as a newer source release, and all observed differences are disclosed rather than normalized away. Existing content-addressed snapshots remain the mechanism for reproducing an earlier release.

### Changes in this step

- Remove the CI-only `data_root=Data` override.
- Keep `workflow/config.yaml` at `data/reference` as the single active default.
- Update user documentation to name the canonical root.
- Add a machine-readable map covering every legacy directory, hashes, release metadata, duplicate groups, and its canonical successor.
- Add tests preventing active workflows from reverting to the legacy root.
- Keep `Data/` frozen until the canonical full-build checks pass; deletion is a separate reviewed commit.

### Acceptance gate

Phase 3 may proceed to legacy-tree deletion only when:

- Python tests pass.
- Snakemake dry run resolves from `data/reference/` without an override.
- Full HTML, PDF, and Shiny CI passes against `data/reference/` on both push and pull-request events.
- The migration JSON parses, covers all 37 legacy dataset directories, and contains no unmapped entries.
- No unexplained scientific output difference remains.
