# Contributing

Thank you for improving the Health Report Generator. Changes must preserve reproducibility, scientific traceability, and audience-appropriate communication.

## Development setup

Follow the root `README.md` for the supported environment and installation commands. Run commands from the repository root.

## Before changing code

1. Create a focused branch from the current default branch.
2. Record whether the change affects data, scientific policy, calculations, presentation, provenance, or only documentation.
3. Do not edit generated files under `results/`; regenerate them through Snakemake.
4. Do not delete or deduplicate source data by filename alone. Compare both data and metadata content, preserve the original snapshot ID, and document every resolution.

## Validation

Run the checks relevant to the change:

```sh
python -m pytest -q
snakemake --dry-run --cores 1
```

For a complete release check, also run:

```sh
snakemake --cores 2
Rscript tests/shiny_smoke.R results/reports/public_health_expert/app
Rscript tests/dashboard_smoke.R results/reports/public_health_expert/app
```

A complete rendering check requires the pinned R, Quarto, and TinyTeX environment described in the root README.

## Change rules

- Keep analysis logic out of presentation templates where possible.
- Add or update tests when calculations, selection rules, schemas, or provenance change.
- Reject unknown configuration keys rather than silently ignoring them.
- Preserve explicit `SKIP`, `WARN`, and `FAIL` meanings in validation output.
- Never convert missing values into zeros unless the scientific policy explicitly defines that transformation.
- Do not describe descriptive changes as causal effects or statistical significance.
- Ensure every audience output retains limitations, exclusions, source information, filters, and generation metadata.
- Update dependency locks deliberately and in the same pull request as dependency declarations.

## Pull requests

Keep pull requests small enough to review independently. Include:

- Purpose and scope.
- User-visible and scientific impact.
- Commands executed and their outcomes.
- Data or provenance changes, including pre/post hashes when applicable.
- Known limitations and follow-up work.

Structural cleanup, data migration, scientific-policy changes, and report redesign should be separate pull requests whenever possible.
