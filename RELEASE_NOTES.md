# Release notes

## Hackathon release

Reproducible, parameterised reporting of FOPH Infectious Diseases Dashboard data: three interactive HTML reports (researcher, health institution, public) from one shared Quarto template, built by one command, each with machine-readable provenance.

### Highlights

- One command: `snakemake --cores 2` (or `bash scripts/health_pipeline/run_all.sh`) builds HTML, PDF and Shiny outputs for every audience listed in `workflow/config.yaml`.
- Audiences differ only by parameter files; analysis tables are byte-identical across them.
- Provenance (`provenance.json`, also embedded in each HTML page) records source, snapshot, release and retrieval dates, filters, effective parameters, versions, Git commit and render time. `release.json` records artifact and code hashes.
- Blocking data-quality gate, content-addressed snapshots, and lineage from every metric to source rows.
- Pinned toolchain (Python 3.11.6, R 4.3.2, Quarto 1.3.353, TinyTeX v2026.10) checked by tests.
- Advanced features: automated weekly API synchronisation (`src/sync_idd_exports.py`), exact-snapshot reproduction offline, a container definition for the optional connector path.

### Development history

| Phase | Outcome |
|---|---|
| 0 Baseline | Reference behaviour, tests and dry run recorded (`docs/phase-0-baseline.md`) |
| 1 Safe hygiene | OS junk removed, documentation and contributor guide added |
| 2 Environment alignment | One Python/R/Quarto/TinyTeX contract with CI checks |
| 3 Canonical data | `data/reference/` made the single data root, with a migration manifest |
| 4 Legacy removal | Retired `Data/` removed in a reversible commit |
| 5 Multi-audience reports | Three audiences, provenance, interactive tables (PR #12) |
| 6 CI hardening | Gated CI jobs, action pinning, secret scan, release verification (branch `ci/phase-6-harden-release-gates`; see `docs/phase-6-ci-hardening.md` once merged) |
| 7 Release polish | Architecture, limitations, demo, citation, release notes, one-command wrapper fix |

### Changes in the release-polish phase

- README rewritten around purpose, quick start, outputs, architecture, data version and limitations; detail moved to `docs/`.
- `scripts/health_pipeline/run_all.sh` is now a real wrapper around Snakemake (it previously pointed at the removed `data/Data` and looped over every stakeholder file, including a retained legacy profile).
- Documentation corrected: weekly CI does synchronise from the public API.
- Added `CITATION.cff`, `docs/architecture.md`, `docs/limitations.md`, `docs/demo.md`, `docs/release-checklist.md`, and tests that keep documentation links, the quick-start command and the citation file valid.

### Known limitations

See [docs/limitations.md](docs/limitations.md). Notably: national totals only, descriptive comparisons, no project licence yet, transitional (non-package) code layout.

### Data

Source: Federal Office of Public Health (FOPH/BAG), Infectious Diseases Dashboard, used with source attribution. The release's exact snapshot id, publication dates and retrieval dates are in each report's provenance.
