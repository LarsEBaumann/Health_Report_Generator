# Phase 2 environment alignment

Phase 2 defines one machine-readable runtime contract and aligns every supported execution path with it.

## Contract

- Python: validated 3.11.6; supported `>=3.11.6,<3.12`
- R: 4.3.2
- Quarto: 1.3.353
- uv: 0.8.14
- TinyTeX: baseline observation 2026.10; actual release version is recorded because CI installation is not byte-locked

The authoritative values are stored in `workflow/toolchain.json`. A regression test checks the Python metadata, Conda metadata, Dockerfile, CI workflows, and setup documentation against this contract.

## Decisions

The existing green full-report CI toolchain is retained as the validated contract. Docker and `pyproject.toml`, which previously required Python 3.14 and Quarto 1.9.38, are aligned to that contract. The optional uv environment remains a separate dependency set from the production Snakemake lock, but both now support the same Python line.

TinyTeX is not described as fully pinned: the setup action installs it dynamically. The workflow records the actual TeX version in release provenance, and the project does not claim byte-identical PDFs across platforms.

## Excluded

- No source data, stakeholder configuration, formulas, selection policy, or templates change.
- No production Python or R package versions change.
- No Quarto upgrade is attempted in this phase.

## Acceptance checks

```sh
python -m pytest -q
uv lock --check
snakemake --dry-run --cores 1 --config data_root=Data
```

A full CI report build and smoke tests are required before merge.
