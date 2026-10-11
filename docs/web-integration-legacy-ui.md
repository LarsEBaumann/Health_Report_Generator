# Legacy UI boundary for SourcePRISM web integration

Recorded: 2026-10-11

## New application path

The new application uses the validated web request adapter and
custom_report.py. It will not dispatch GitHub Actions for visitor requests
or require visitor GitHub credentials.

Dockerfile.report no longer installs the UI dependency lock.
Its rebuilt image passed:
- Marimo module, executable and distribution absence checks.
- Dependency compatibility checks.
- The complete 159-test Python suite.
- A fresh adapter-generated researcher report.

## Intentionally retained legacy components

- Dockerfile: optional Marimo environment/version-check image.
- compose.yaml ui profile: legacy development tooling, not the new app.
- pyproject.toml and uv.lock: legacy optional UI environment.
- requirements.ui.in and requirements.ui.lock.txt: legacy UI dependencies.
- render-selected-report.yml: manually dispatched selected-lineage workflow.

These are excluded from the intended new production application path.
Their presence in the repository does not imply deployment approval.

## Preserved scientific automation

- refresh-idd-data.yml: data refresh, validation, scientific rendering,
  release verification and source-snapshot commits.
- validate.yml: fast, secrets, container and full jobs.

The required container job now builds the report image and checks its
tools and absence of Marimo. Existing audience rendering, release checks,
packaged-app checks and no-op rebuild checks remain in place.

The legacy UI image is no longer smoke-tested by that required job.
Legacy UI compatibility is therefore not guaranteed by the new check.

## Verification status

- Report-image runtime check passed locally without a source bind mount.
- Edited workflow YAML parsed locally.
- Scientific container steps remained present.
- Remote GitHub Actions execution has not yet been verified.
- Production Compose and application services are not yet implemented.
