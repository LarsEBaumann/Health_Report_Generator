# Data directories

The repository currently contains two source-data roots with different roles and histories. Do not treat them as interchangeable.

## `data/reference/`

This is the default source configured in `workflow/config.yaml`. It contains the broader automatically synchronized IDD reference collection, including retrieval metadata where available.

## `Data/`

This is the legacy committed source used by the main validation workflow through `--config data_root=Data`. It contains duplicate-suffixed directories and two unexpectedly nested exports. It remains in place until a separately reviewed migration proves that scientific outputs and provenance are preserved.

## Generated data

The pipeline writes generated snapshots, harmonised data, checks, analysis bundles, and reports under `results/` by default. Generated results are ignored by Git and must not be manually promoted to source data.

## Safety policy

Before moving, deleting, or deduplicating source data:

1. Record the source commit and snapshot ID.
2. Hash both `data.csv` and associated metadata/retrieval files.
3. Produce a machine-readable mapping from every old path to its retained path or documented removal.
4. Run validation with zero `FAIL` results.
5. Compare pre/post analysis-table contents and hashes.
6. Explain every intentional difference.
7. Retain enough source and provenance information to reproduce the previous release.

The Phase 0 inventory is recorded in `docs/phase-0-baseline.md`.

## Licensing

The repository does not currently state a project-wide license. Source datasets may have their own terms. Preserve publisher metadata and verify applicable source and project licensing before redistribution or release.
