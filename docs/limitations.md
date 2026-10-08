# Limitations

These apply to every audience. Reports state the ones relevant to reading the numbers; this page adds the technical and project limits.

## Interpreting the data

- **Notifications are not infections.** Counts are officially reported cases. Testing, clinician awareness and reporting practice affect them. A rise can mean more disease, more testing, or both.
- **Descriptive only.** Changes are percentage differences against a reference year. There are no significance tests, confidence intervals or causal claims.
- **Influenza dominates the viral group.** The viral change is +124% (2025 vs 2019) with influenza and −3% without it. The reports show both. The data cannot explain why.
- **Recent years can be revised.** The publisher may update counts as late notifications arrive. The snapshot id pins exactly which release a report used.
- **Small numbers.** Percentages for diseases with few cases swing widely. The monitoring report flags fewer than 20 cases in either year; this is a display rule, not a statistical threshold.
- **Excluded series.** COVID-19 (no 2019 baseline) and AIDS (a stage of HIV) are left out of group totals. Sentinella estimates are shown as context and never added to mandatory notifications. Series that fail completeness rules (incomplete year or months, missing population, missing `dataComplete`) are excluded and listed with reasons in each methods report.
- **Classification is curated by the project team.** `pathogen_class.csv` assigns diseases to viral or bacterial; no external scientific review has been recorded. Unclassified datasets are excluded rather than guessed.
- **Rates differ slightly from publisher rates**, which use unrounded figures.

## Scope

- **National totals only** (Switzerland plus Liechtenstein, `CHFL`). The schema accepts `CH` or `CHFL`. Canton-level series exist for some diseases but not all selected ones, so no canton view was invented. A Switzerland-only scope would drop influenza (no complete 2019 baseline) and change the viral headline, so it is not used.
- **Annual comparison only.** No weekly alert levels, seasonal thresholds, age or sex breakdowns, or maps.
- **The operational report is not an outbreak detector.** It ranks changes between two years and does not replace local surveillance.

## Reproducibility

- **Reproduction means the same snapshot, code and toolchain.** Changed data give changed reports. Hashes cannot recover deleted inputs, so retain the snapshot folder.
- **R packages.** The lockfile `renv.lock` is authoritative. Other R installations (for example conda) can produce slightly different package versions and, in principle, differences in figures.
- **PDF builds need the pinned TinyTeX.** Quarto automatic TeX installation is disabled so incomplete installations fail loudly.
- **Linux CI is the reference platform.** The secret scan and container job target Linux x86_64.

## Project

- **No project licence is stated yet** (see `data/README.md`); the source data carry their own terms (source attribution).
- **Interactivity is client-side.** HTML tables are filterable and sortable and the Shiny app is reactive, but there is no hosted service. Sharing a folder does not deploy anything.
- **Code layout is transitional.** Modules are not yet an installable package, and the optional Marimo interface is experimental.
- **Historical prototypes remain in the repository** (`example_output/`, `Health_Report_Generator-test/`, `design/`) and are not release evidence.
