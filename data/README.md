# Data directories

## Canonical live source

`data/reference/` is the only active source-data root. It is the default in `workflow/config.yaml`, and CI uses that default without an override. The directory contains the broader synchronized IDD reference collection and associated publisher metadata.

Treat each update as a new source release. Do not edit files in place without retaining their source metadata and recording the resulting content-addressed snapshot.

## Legacy source

`Data/` is a frozen legacy release. It is no longer read by production workflows or CI. Phase 0 identified duplicate-suffixed directories and unexpectedly nested exports in that tree.

The machine-readable disposition of every legacy dataset directory is recorded in `docs/phase-3-data-migration.json`. The legacy tree remains temporarily in this branch so the canonical switch can pass full CI before a separately reviewable deletion commit. Git history and the Phase 0 snapshot ID preserve its previous state.

## Generated data

The pipeline writes generated snapshots, harmonised data, checks, analysis bundles, and reports under `results/` by default. Generated results are ignored by Git and must not be manually promoted to source data.

## Migration safety

Canonicalization is a source-release change, not a byte-preserving rename. The two roots have different publisher dates and file hashes. Their selected reports have the same row counts and topic set, but some 2022–2025 values and 2025 population denominators differ. Those differences are documented in `docs/phase-3-data-migration.json` and must not be hidden as deduplication.

Before deleting the frozen `Data/` tree:

1. Merge or otherwise preserve the Phase 0 baseline commit and snapshot ID.
2. Retain the machine-readable path and hash map.
3. Run full HTML, PDF, and Shiny validation against `data/reference/` with zero failures.
4. Review the documented scientific differences.
5. Delete `Data/` in a separate commit so the destructive step is easy to audit and revert.

## Licensing

The repository does not currently state a project-wide license. Source datasets may have their own terms. Preserve publisher metadata and verify applicable source and project licensing before redistribution or release.
