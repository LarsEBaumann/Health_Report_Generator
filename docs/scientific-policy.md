# Scientific policy and data contract

Rules that decide which data enter a report and how numbers are calculated. Audience wording never changes these; see [audiences](audiences.md).

## Quality and selection policy

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

Copy a stakeholder JSON, set a unique `id`, and add the filename stem to `workflow/config.yaml`. Filename stem and ID must match. `public_health_expert.json` is retained as the analytic base profile for the on-demand selected-report workflow (`render_selected.py`); it is no longer part of the default build. Only supported settings pass `workflow/config.schema.json`; unsupported geographies, periods, classes, sections, and unknown keys fail clearly. Change presentation sections with `outputs`. Arbitrary new analyses require code plus tests, not an ignored configuration field.

See [SCHEMA.md](../scripts/health_pipeline/SCHEMA.md) for table keys, types and calculation lineage. `pathogen_class.csv` remains a curated lookup: review classifications and the note column before adding topics. Unclassified datasets are explicitly excluded, never relabelled as syndromic. The current classifications were supplied by the team; no scientific reviewer approval is invented.
