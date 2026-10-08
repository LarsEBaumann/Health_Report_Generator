# Phase 3 — canonical data root

## Decision

`data/reference/` is the canonical live input root. The default workflow already used it, while CI overrode the default with the older uppercase `Data/` tree. Phase 3 removes that override so local execution and CI read the same source release.

This is not described as deduplication. The roots are not byte-identical: `data/reference/` is broader and newer. The legacy tree is frozen and will be removed only in a separate, reviewable commit after the canonical build is green.

## Pre-migration evidence

The comparison was run from main commit `1aeb1a1414bcbf94ae8acf8288565f5edf21cf71` with the `tables` target against both roots.

| Property | Legacy `Data/` | Canonical `data/reference/` |
|---|---:|---:|
| Snapshot ID | `f1484622df74831453d66fb36cfc9fab002bd0695385195143930328d4f74653` | `d0709708a8057815801497701bfaa145017979f1ecace4508ae46237438573ee` |
| Dataset directories | 37 | 56 |
| Unique data/metadata byte pairs | 20 | 56 |
| Selected report series rows | 72 | 72 |
| Selected report metric rows | 296 | 296 |

The selected topic set and pathogen classification table are unchanged. Scientific table bytes are not identical: 14 series rows differ, including four count rows, twelve population rows, and fourteen calculated incidence rows. Differences are concentrated in revised 2022–2025 counts and 2025 population denominators. The complete hashes and path-level dispositions are in `docs/phase-3-data-migration.json`.

## Safety interpretation

Equal row counts do not establish data equivalence. The canonical root is accepted as a newer source release, and all observed differences are disclosed rather than normalized away. Existing content-addressed snapshots remain the mechanism for reproducing an earlier release.

## Changes in this step

- Remove the CI-only `data_root=Data` override.
- Keep `workflow/config.yaml` at `data/reference` as the single active default.
- Update user documentation to name the canonical root.
- Add a machine-readable map covering every legacy directory, hashes, release metadata, duplicate groups, and its canonical successor.
- Add tests preventing active workflows from reverting to the legacy root.
- Keep `Data/` frozen until the canonical full-build checks pass; deletion is a separate reviewed commit.

## Acceptance gate

Phase 3 may proceed to legacy-tree deletion only when:

- Python tests pass.
- Snakemake dry run resolves from `data/reference/` without an override.
- Full HTML, PDF, and Shiny CI passes against `data/reference/` on both push and pull-request events.
- The migration JSON parses, covers all 37 legacy dataset directories, and contains no unmapped entries.
- No unexplained scientific output difference remains.
