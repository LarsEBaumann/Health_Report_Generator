# Data directories

## Canonical live source

`data/reference/` is the only active source-data root. It is the default in `workflow/config.yaml`, and CI uses that default without an override. The directory contains the broader synchronized IDD reference collection and associated publisher metadata.

Treat each update as a new source release. Do not edit files in place without retaining their source metadata and recording the resulting content-addressed snapshot.

## Retired legacy source

The frozen `Data/` release was removed in Phase 4 after the canonical-root migration passed full push and pull-request CI. It is not an accepted runtime input and must not be recreated.

The machine-readable disposition of every former legacy dataset directory remains recorded in `docs/phase-3-data-migration.json`. `docs/phase-4-legacy-removal.json` records the removal gate and deletion commit. Git history and the Phase 0 snapshot ID preserve the previous state for audit and recovery.

## Generated data

The pipeline writes generated snapshots, harmonised data, checks, analysis bundles, and reports under `results/` by default. Generated results are ignored by Git and must not be manually promoted to source data.

## Migration safety

Canonicalization was a source-release change, not a byte-preserving rename. The two roots had different publisher dates and file hashes. Their selected reports had the same row counts and topic set, but some 2022–2025 values and 2025 population denominators differed. Those differences remain documented in `docs/phase-3-data-migration.json` and must not be described as simple deduplication.

The removal is reversible through Git history, but restoration is not part of the supported production workflow. Any proposed restoration must explain why the older source release is scientifically required and must use a distinct archival path rather than reintroducing an ambiguous active root.

## Licensing

The repository does not currently state a project-wide license. Source datasets may have their own terms. Preserve publisher metadata and verify applicable source and project licensing before redistribution or release.
