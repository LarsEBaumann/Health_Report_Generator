# Report bundle contract, version 2.0

All CSVs are UTF-8, comma-delimited, with one header row. Empty numeric fields mean missing/undefined, never zero. Identifiers and paths are strings; years and source record positions are integers; values are floating-point numbers. `bundle.json` provides SHA-256 checksums for all data/config files and a snapshot identifier. A bundle is ready only when this manifest exists and all hashes match.

| File | Key | Contents |
|---|---|---|
| series.csv | topic, year | Selected national count, population, calculated incidence, geography, measure, source, coverage, aggregation and metric references |
| metrics.csv | metric_id | Metric type, subject, year, unit, value, formula, ordered inputs_json |
| lineage.csv | metric_id plus input relationship | Derived metric edges, or raw file/record/column references and full data/metadata hashes |
| selection.csv | dataset_id | Inclusion/exclusion, reason, and main-group eligibility |
| sources.csv | source_file | Dataset identity, snapshot, full checksums, publication date, status and used flag; duplicate downloads remain visible |
| checks.csv | dataset_id, check, detail | PASS, WARN, FAIL or SKIP with a reason; several period comparisons may share a check name |
| stakeholder.json | id | Effective analysis policy and section configuration |
| pathogen_class.csv | topic | Curated class, label and rationale/note |
| snapshot.json | snapshot_id | Exact raw files, sizes and hashes; snapshot paths are relative to the archive root |

`series.csv` can include reference/base years outside the reporting window. All series have complete coverage for the union of those years. Population and count units remain distinct. The report does not pool consultations with mandatory case notifications.

## Formulas

- `raw_sum`: sum of raw values identified by all raw lineage edges (annual row or 12 monthly rows).
- `raw_identity`: exact value in the identified raw record, used for a population denominator. For monthly aggregation all 12 denominators must first agree.
- `sum`: sum of the ordered input metrics.
- `ratio_100`: first input / second input * 100; group index baseline must be positive.
- `ratio_100000`: first input / second input * 100000; population must be positive.
- `percent_change`: (second input - first input) / first input * 100. Zero first input produces a missing value, never infinity or a false zero change.

Every derived metric is a directed edge to other metric IDs. Every leaf points to archived source records, including population leaves. The snapshot and bundled settings/classification explain which candidates were selected; the release manifest records the implementation and environment used to execute those formulas.

The report prints short `M<number>` references mapped to full metric IDs in its appendix. These references are presentation-local, not persistent IDs. Use full IDs with the snapshot/config identity for machine comparisons.

## Compatibility

The old wide `report_*_table.csv` and count-only trace CSV have been replaced by these normalised tables. HTML, PDF and Shiny must consume these tables rather than repeat disease selection or group calculations. Shiny filters change presentation only; a different analysis policy requires a new pipeline build.
