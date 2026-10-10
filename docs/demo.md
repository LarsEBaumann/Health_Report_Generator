# Demo walkthrough

A 5 to 10 minute tour. Run `snakemake --cores 2` first (see the README), or use a downloaded CI artifact `health-report-<sha>`.

## 1. Same data, three readers (2 min)

Open the three reports side by side:

1. `results/reports/researcher/report.html`: effective parameters, coverage, quality checks, methods, all disease results.
2. `results/reports/health_institution/report.html`: the monitoring summary lists the diseases with the largest changes in case counts.
3. `results/reports/public/report.html`: plain headline, charts and the "How sure can we be?" section.

Point out that the viral and bacterial headline numbers (+124% and +21% for 2025 vs 2019) are identical in all three.

## 2. Uncertainty is not hidden (2 min)

- Public report: scroll to "How sure can we be?". It explains reported cases versus infections, testing effects and revisions.
- Look at the chart "Viral, without influenza": the viral rise becomes −3%.
- Researcher report: the quality-check counts (PASS, WARN, SKIP) and the exclusion table.

## 3. Provenance (2 min)

In any report, open the "Provenance" section, then click "Download provenance (JSON)". Or from a terminal:

```sh
python -c "import json;p=json.load(open('results/reports/public/provenance.json'));print(p['data']['snapshot_id'],p['data']['retrieved_at_utc_range'],p['code']['git_commit'],p['rendered_at_utc'])"
```

Show that the same JSON is embedded in the page: in the browser console, `JSON.parse(document.getElementById('report-provenance').textContent).stakeholder.id`.

## 4. Add an audience without touching the template (3 min)

```sh
cp scripts/health_pipeline/config/stakeholders/public.json scripts/health_pipeline/config/stakeholders/clinicians.json
# edit: "id": "clinicians", title, question, presentation.display_name, and "outputs"
# add "- clinicians" under stakeholders in workflow/config.yaml
snakemake --cores 2 results/reports/clinicians/report.html
```

A fourth report appears with its own provenance. The `id` must equal the file name. Remove the file and the config entry afterwards (a committed fourth audience needs a test update: the default build is asserted to contain exactly the three audiences).

## 5. A custom request, built once and reused (3 min)

```sh
docker compose run --rm report python scripts/health_pipeline/custom_report.py \
  examples/request-2022-2025.json --out results/custom
docker compose run --rm report python scripts/health_pipeline/custom_report.py \
  examples/request-2022-2025.json --out results/custom2
```

The first run prints `cache miss` and renders. The second prints `cache hit` with the same key in a few seconds, and `results/custom2` is identical to `results/custom`, including the original render time. Open `results/custom/report.html`: the title reads "Custom request: 2022 to 2025". Then compare the two provenance files:

```sh
python -c "import json;p=json.load(open('results/custom/provenance.json'));print(p['filters']['years'],p['effective_parameters']['title'])"
python -c "import json;r=json.load(open('results/custom/request_provenance.json'));print(r['cache_key'][:12],list(r['components']),r['rendered_utc'])"
```

The reference year stays 2019, so a 2022 to 2025 report is still compared with the pre-COVID baseline. This is a stated choice, and a request can change `reference_year` and `index_base_year`.

## 6. Reproduce a past release (optional)

Use the snapshot command in [reproduction.md](reproduction.md#reproduce-a-specific-archived-release) with an earlier `results/snapshots/<id>/manifest.json`.
