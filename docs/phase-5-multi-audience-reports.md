# Phase 5 — multi-audience reports

## Scope

Generate researcher, operational (health institution) and public interactive HTML reports from one shared report source, differentiated only by stakeholder parameter files, with machine-readable provenance in every output.

Out of scope, unchanged: packaging refactors, scientific calculations, source data, historical files (`public_health_expert.json` and `example_output/` are retained).

## Design decisions

- **One template.** `scripts/health_pipeline/report_public_health_expert.qmd` (plus the shared `methods.qmd` companion and R helpers) renders every audience. Snakefile declares it once as `SHARED_TEMPLATE`.
- **Three parameter files.** `researcher.json` (`technical`/`full`), `health_institution.json` (`dashboard`/`monitoring`), `public.json` (`editorial`/`plain_language`). They differ in `title`, `question`, `outputs` and `presentation` only.
- **Identical analytic parameters.** All three use the analytic settings of the historical `public_health_expert` profile. The analysis tables (`metrics.csv`, `series.csv`, `lineage.csv`, `selection.csv`) are byte-identical across audiences, and `metrics.csv` matches the Phase 3 canonical hash `e4e37ba8…`. Findings therefore agree across audiences; only communication differs.
- **Operational geography.** The schema supports `CH` or `CHFL` national totals only. Canton-level series exist for some diseases but not all selected ones, so no canton subset was invented. A `CH` scope was tested: influenza has no complete CH-level 2019 baseline and is excluded, changing the viral headline from +124% to −3%. Because that difference is a data-availability artefact, not a scope choice, `CHFL` is kept for all audiences and the limitation is stated in the monitoring summary.
- **Uncertainty is translated, not hidden.** Every audience shows quality-check counts (PASS/WARN/SKIP/FAIL), limitations and provenance. The operational brief flags small numbers (< 20 cases in either year; a display rule, not a statistical test). The public report adds a plain-language “How sure can we be?” section, including the influenza sensitivity comparison.
- **Provenance.** `publish.py` writes `provenance.json` (HTML) and `provenance.pdf.json` (PDF) beside each report and embeds the HTML record as `<script type="application/json" id="report-provenance">`. See README “Provenance format”.
- **Interactivity.** Dependency-free script: every report table can be filtered and sorted; documents have contents navigation and expandable details. The Shiny app remains the fully reactive option.
- **Selected-report compatibility.** `render_selected.py` and `src/artifact_download.py` use the `researcher` lineage bundle and fall back to `public_health_expert` for artifacts built before Phase 5.

## Acceptance gate

- `python -m pytest -q` passes, including `tests/test_audiences.py` (three audiences enabled, schema-valid, distinct presentations, shared analytic parameters, single shared template, canonical data root, provenance wiring and record contents, lineage fallback).
- `snakemake -n` resolves 3 × (analyse, render_html, render_pdf, package_shiny) from `data/reference/`.
- Full `snakemake --cores 2` builds HTML, PDF, Shiny packages and `release.json`.
- `python scripts/health_pipeline/check_outputs.py` confirms exactly three audience HTML reports with embedded and sidecar provenance.
- `tests/shiny_smoke.R` and `tests/dashboard_smoke.R` pass against `results/reports/researcher/app`.
