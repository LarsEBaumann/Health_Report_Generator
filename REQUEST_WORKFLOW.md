# Selected-dataset reports (request v1.0)

This is the new request-driven route. The original demo remains available by running Snakemake without `request_file`. Marimo integration and detailed audience-specific layouts remain separate work.

## Run locally

Use the repository's existing environment setup in GETTING_STARTED.md. From the repository root:

```sh
snakemake --cores 2 --config request_file=examples/requests/public-health.json
```

The example requests influenza mandatory surveillance and Lyme Sentinella, independently. To change the request, copy that JSON and edit it:

```json
{
  "schema_version": "1.0",
  "request_id": "my-report-001",
  "audience": "researcher",
  "datasets": ["INFLUENZA_oblig", "INFLUENZA_sentinella", "LYME_sentinella"],
  "formats": ["html", "pdf"]
}
```

Audience is `researcher`, `public_health_expert`, or `general_public`. Formats are `html` and/or `pdf`. Request IDs use letters, numbers, hyphens or underscores. Unknown fields, duplicate JSON keys and repeated dataset IDs are rejected. The schema is in `workflow/request.schema.json`.

Dataset IDs identify exports, not broad disease groups: mandatory influenza and Sentinella influenza remain separate. The generated `data/catalogue.csv` lists available IDs and source identities. Exact duplicate download folders ending in ` (1)`, ` (2)`, etc. resolve to the same ID only when their source identities agree; conflicting exports fail.

## What happens

1. Validate JSON.
2. Freeze and fingerprint raw CSV/metadata files, or verify a specified archived snapshot.
3. Prepare all snapshot datasets once, retaining their original row numbers. Reuse this prepared snapshot for later requests.
4. Resolve exactly the requested dataset IDs. Check the selected datasets; unrelated quarantined datasets do not block the request.
5. Select explicit national totals, cases before consultations, then the finest available supported frequency. Record those choices. Keep sources separate; do not calculate viral/bacterial totals or require a baseline year.
6. Write independent time series, coverage, selection, sources, checks and row-level lineage CSVs.
7. Render the shared Quarto template using ggplot2, only in the requested formats.
8. Write `result.json` only when the requested outputs exist. It lists relative artifact paths and their checksums.

Current scope: national case/consultation trends from this infectious-disease metadata structure. This is not an arbitrary-CSV analyser. Wastewater, sequencing, positivity and sources without explicit national totals need reviewed adapters. They fail with an explanation rather than disappearing from the report. Selecting several datasets does not make their values comparable or additive.

Missing periods and missing values remain missing, not zero. Source completeness is retained as complete/incomplete/unknown. Population and 2019 observations are not prerequisites. All available periods are used; date/geography/plot controls are not part of v1.0.

## Find and share the output

Look in `results/requests/<request_id>-<request_hash>/`:

- `report.html` and/or `report.pdf`: requested documents.
- `report.<format>.provenance.json`: full per-render provenance.
- `data/`: analysis CSVs, original request, resolved settings, snapshot manifest and integrity manifest.
- `render-source/`: editable shared QMD and the data/provenance used for its first requested format.
- `result.json`: success and artifact manifest for the GUI to consume.

The HTML embeds its plots and a JSON provenance record, so its charts and provenance travel with the file. The PDF includes a compact JSON provenance appendix; keep its sidecar and the data bundle for full lineage. Neither document embeds the entire raw snapshot. Reproduction requires that snapshot and the code/environment as well.

The current audience variants share the same analysis and plots with modest wording differences. They are placeholders for the reporting colleague's designs. Request-driven Shiny and plot-type selection are not yet implemented. The original demo Shiny package remains on the legacy route.

## Reuse a snapshot and cache

```sh
snakemake --cores 2 --config request_file=my-request.json snapshot_manifest=results/snapshots/<snapshot_id>/manifest.json
```

`results/cache/prepared/` holds prepared data keyed by source snapshot, preparation code/environment files and Python/pandas/pyarrow versions. Changing the audience or selected datasets reuses that preparation. Its checksums are verified before reuse. Changing source bytes or preparation dependencies creates a different cache entry. Report tables are rebuilt for each new request; cache reuse does not bypass selected-data checks.

Keep the output directory between local runs. A fresh GitHub-hosted runner currently prepares data again: cross-run data caching is deliberately not configured yet. Package download caching is separate from analysis caching.

## GitHub Actions handoff (Marimo colleague)

The new `request-report.yml` workflow accepts one string input, `request_json`, containing the same JSON. It parses that input as data; it does not insert it into shell code. Dispatch the workflow with the intended branch as `ref`. GitHub requires a dispatchable workflow to exist on the default branch; adding it only on a test branch may not expose a Run workflow button until it is merged there.

The artifact also includes the frozen raw snapshot, but excludes the prepared-data cache. After a successful run, download `requested-health-report-<run_id>` and locate `result.json`. Use its HTML path to display the report. Poll run completion before downloading; a submitted request is not a successful report. Keep tokens in the local Marimo server or another backend, never in static HTML or committed JSON.

This change provides the backend interface; it does not modify the Marimo app or deploy anything.

## Test before merging

```sh
python -m pytest -q
snakemake --cores 2 --config request_file=examples/requests/public-health.json
snakemake -n --cores 2 --config request_file=examples/requests/public-health.json
```

The last command should say nothing needs to run. Then try a different request using the same snapshot: preparation should be reused while analysis/rendering runs. Try an unknown dataset and confirm the run fails rather than returning the original demo. Do not treat old output files as a fresh success; use the exit status of the current workflow and its final artifact upload.
