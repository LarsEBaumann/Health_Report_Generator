# Phase 7 — hackathon release documentation

## Scope

Final documentation and release polish. No change to data, scientific calculations or report content.

## Deliverables

- README rewritten as an entry point: purpose, quick start, outputs, architecture diagram, data source and version, headline limitation, documentation index. Detailed material moved, unchanged apart from path fixes, into `docs/reproduction.md`, `docs/scientific-policy.md` and `docs/audiences.md`. The "Tests and release discipline" section is kept as it was.
- New: `docs/architecture.md` (data-flow diagram and design decisions), `docs/limitations.md`, `docs/demo.md`, `docs/release-checklist.md`, `RELEASE_NOTES.md`, `CITATION.cff`.
- `data/README.md`: source, terms (public use with source attribution, per the FOPH IDD data page), acquisition, layout, version location. The project licence is deliberately left to the repository owner.
- `scripts/health_pipeline/run_all.sh` fixed to be the documented thin Snakemake wrapper. It previously defaulted to the retired `data/Data` and ran every stakeholder file through a legacy script.
- Corrected a stale claim that CI never fetches new data; the weekly workflow synchronises from the public API.
- `tests/test_release_docs.py`: relative links and heading anchors resolve; the README names the one command and every configured audience's report path; `run_all.sh` dry-runs all audiences and avoids retired paths; the citation file is valid; data terms and key limitations are stated; headline numbers quoted in the docs match the smoke test.

## Not done (decisions for the maintainer)

- No `LICENSE` file: the licence is the owner's choice.
- No version tag or GitHub release: see `docs/release-checklist.md`.
- `CITATION.cff` uses the GitHub handle as author alias; replace it with full names and add a version and release date when tagging.
- Package refactor and removal of historical prototypes remain out of scope (see limitations).

## Acceptance gate

A fresh clone follows the README quick start and produces the three audience reports with provenance; documentation links resolve; `python -m pytest -q` passes.
