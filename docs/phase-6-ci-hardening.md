# Phase 6 — CI hardening and release gates

## Scope

Make a release impossible to publish unless tests and the three-audience build pass, and make
every uploaded artifact verifiable against its recorded hashes and provenance. No change to
data, scientific calculations or report content.

## CI jobs (`.github/workflows/validate.yml`, on push and pull_request)

| Job | Needs | Gate |
|---|---|---|
| `fast` | — | `ruff check .` (pinned in `scripts/ci/requirements-lint.txt`), `python -m pytest -q` (unit, schema, audience, environment and CI contract tests), `snakemake --dry-run` |
| `secrets` | — | Full-history scan with gitleaks 8.30.1, downloaded and SHA-256 verified by `scripts/ci/secret_scan.sh` |
| `container` | `fast` | `docker build` of the `Dockerfile`, then a smoke run of its default command (`uv sync --locked`, Quarto and Marimo versions) |
| `full` | `fast` | Full `snakemake --cores 2`; `check_outputs.py`; `verify_release.py`; Shiny and dashboard smoke tests; rebuild dry run must report “Nothing to be done”; upload of `results/` only after all of these succeed (`if-no-files-found: error`) |

`update-lyme-data.yml` runs the same output and release verification before uploading the
lineage artifact consumed by the selected-report UI.

## Release verification (`scripts/health_pipeline/verify_release.py`)

- Every artifact hash in `release.json` matches the file on disk; every produced file is recorded.
- Each audience's `provenance.json` and `provenance.pdf.json` bundle hashes match `data/`; the
  shared-template and parameter hashes match the source files.
- The provenance embedded in each HTML page equals its `provenance.json` sidecar.
- Every local link and asset in rendered HTML resolves, including `#anchor` targets; pages load no
  remote scripts, stylesheets or images. External hyperlinks are not fetched (CI must not depend
  on third-party availability).

`tests/test_ci_contract.py` proves the verifier rejects tampered artifacts, unrecorded files,
tampered bundles, broken links, missing anchors, remote assets and embedded-provenance drift.

## Supply chain

- All actions in all workflows are pinned to full commit SHAs with a version comment; a test
  rejects tag references. `.github/dependabot.yml` proposes weekly grouped updates.
- Ruff, gitleaks, TinyTeX and Quarto are version-pinned; downloaded binaries are checksum-verified.
- Ruff enforces pyflakes and syntax rules (`E9`, `F`) only; formatting is not enforced to avoid a
  repository-wide rewrite. Stricter rules can be enabled incrementally.

## Branch protection guidance (repository admin; not set by code)

Protect `main` (Settings → Branches, or a ruleset):

- Require a pull request before merging, with at least one approving review; dismiss stale approvals.
- Require status checks to pass and the branch to be up to date: `fast`, `secrets`, `container`, `full`.
- Block force pushes and deletion; include administrators.

Equivalent API call (adjust reviewers as needed):

```sh
gh api -X PUT repos/LarsEBaumann/Health_Report_Generator/branches/main/protection \
  -H "Accept: application/vnd.github+json" --input - <<'JSON'
{"required_status_checks":{"strict":true,"contexts":["fast","secrets","container","full"]},
 "enforce_admins":true,
 "required_pull_request_reviews":{"required_approving_review_count":1,"dismiss_stale_reviews":true},
 "restrictions":null,"allow_force_pushes":false,"allow_deletions":false}
JSON
```

The selected-report and data-update workflows keep `ref: main`, so they only ever build protected code.

## Acceptance gate

- `ruff check .`, `python -m pytest -q` and `snakemake --dry-run` pass.
- Full build, `check_outputs.py`, `verify_release.py`, Shiny and dashboard smoke tests pass; rebuild is a no-op.
- Secret scan reports no leaks.
- On the pull request, all four jobs pass on both push and pull_request events.
