# Phase 1 safe hygiene

Phase 1 improves repository clarity without changing scientific calculations, source data, workflow configuration, or generated report behavior.

## Included

- Contributor guidance and validation expectations.
- Data-root documentation and a destructive-change safety gate.
- A repository map classifying production, optional, experimental, legacy, and historical paths.
- Explicit notices in historical output/prototype directories.
- Removal of tracked operating-system metadata files.

## Excluded

- No source datasets are moved, renamed, deduplicated, or deleted.
- No environment versions or dependency locks are changed.
- No stakeholder parameters, formulas, selection rules, schemas, or templates are changed.
- No historical prototype is deleted in this phase.

## Acceptance checks

```sh
python -m pytest -q
snakemake --dry-run --cores 1 --config data_root=Data
```

A full CI build remains required before merging.
