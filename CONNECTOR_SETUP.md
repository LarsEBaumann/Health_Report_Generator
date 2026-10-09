# Optional GitHub-backed Marimo interface

This interface is separate from local report generation.
For credential-free local reports, follow README.md or GETTING_STARTED.md.

The interface downloads a versioned artifact from a configured GitHub
repository, presents eligible datasets, and requests a selected report
through that repository's GitHub Actions workflow.

Local container report generation has been tested separately.
Configuration, request-target, and UI-error paths have automated tests.
A real fork-backed download and workflow dispatch must still be verified
before claiming end-to-end connector success.

## 1. Prepare your repository

1. Fork the repository into an account or organization you control.
2. Enable GitHub Actions in the fork.
3. Ensure the repair changes exist in the fork's `main` branch:
   the UI, selected-report workflow, and renderer must use matching audience IDs.
4. Run the workflow defined in `.github/workflows/update-lyme-data.yml`
   on the fork's `main` branch.
5. Wait for successful completion and confirm that it produced the
   `health-report-<run-id>` artifact.

Actions and scheduled workflows may need enabling separately in a fork.
Do not assume the weekly schedule is running merely because the fork exists.

During development, do not switch away from your repair branch or merge
untested changes merely to follow this guide. Complete local checks first.
The selected-report workflow currently checks out `main`, so dispatching
it from another ref does not by itself test that ref's renderer code.

## 2. Configure repository selection

Run from your local checkout of the repository you intend to use:

```bash
export GITHUB_REPOSITORY='YOUR_OWNER/YOUR_FORK'
```

Replace both placeholders with the actual fork owner and repository name.

Selection precedence:

1. Non-empty `GITHUB_REPOSITORY`, in `owner/repo` form.
2. Otherwise, `GITHUB_OWNER` and `GITHUB_REPO`.
3. Legacy defaults: `LarsEBaumann/Health_Report_Generator`.

Malformed primary configuration fails explicitly rather than falling back.
Always set `GITHUB_REPOSITORY` for a fork and confirm the target shown in the UI.

Optional settings, normally left at their defaults:

```bash
export GITHUB_BRANCH=main
export GITHUB_APP_REF=main
export GITHUB_WORKFLOW=update-lyme-data.yml
```

`GITHUB_BRANCH` selects source workflow runs.
`GITHUB_APP_REF` selects the workflow-dispatch ref.
The current selected-report workflow checks out `main` internally.

## 3. Supply your own personal access token

Create a fine-grained GitHub personal access token authorized for your fork,
with Actions read/write permission. Organization policy or token approval
requirements may also apply.

This is a personal access token, not a private key.
Do not put it in Git, source code, notebook cells, reports, or provenance.

Read it without echoing it or putting its value into shell history:

```bash
read -rsp 'GitHub token: ' GITHUB_TOKEN; echo
export GITHUB_TOKEN
```

Anyone using a fork supplies their own token.
Do not distribute the original author's token.

## 4. Build and start the optional UI

Docker and Docker Compose must be installed and accessible.
The UI service uses the original Dockerfile and its locked uv environment.
It does not use the report pipeline's Python environment.

```bash
export LOCAL_UID="$(id -u)"
export LOCAL_GID="$(id -g)"

docker compose --profile ui build ui

docker compose --profile ui run --rm \
  -p 127.0.0.1:2718:2718 ui \
  sh -lc 'mkdir -p /tmp/report-home/.config /tmp/report-home/.cache /tmp/report-home/.local/share &&
  export HOME=/tmp/report-home XDG_CONFIG_HOME=/tmp/report-home/.config XDG_CACHE_HOME=/tmp/report-home/.cache XDG_DATA_HOME=/tmp/report-home/.local/share &&
  uv sync --locked &&
  uv run marimo run src/ui.py --host 0.0.0.0 --port 2718 --show-tracebacks'
```

Open http://127.0.0.1:2718 and keep the terminal running.
The port is bound to the local host, not intentionally published to the network.

Before submitting anything, confirm that the UI displays your intended fork.

No manual `gh run download`, `data/lineage` directory, or shell
`LINEAGE_RUN_ID` setting is required. The downloader queries GitHub directly.

## 5. Understand source artifact selection

The downloader queries

up to 20 successful runs of the configured source
workflow and branch, then chooses the successful run with the largest
run number among those returned.

It expects a non-expired artifact named `health-report-<run-id>`.
It does not currently search older runs if that selected run's artifact
is missing or expired.

Artifacts have 30-day retention in the current workflows.
If the required artifact has expired or is missing, run the source
data-update workflow again and verify successful artifact creation.

The default data-bundle preference is `researcher`, with historical
`public_health_expert` fallback. This compatibility fallback is not a
new selectable audience.

## 6. Request and retrieve a report

Choose one canonical audience:

- `researcher`
- `health_institution`
- `public`

Select at least one eligible bacterial or viral dataset, then click
Generate report. This creates an Actions workflow run in the configured
repository; it is not a local-only operation.

The request records the source run ID selected by the downloader.
The workflow input `lineage_run_id` remains necessary for exact artifact
selection, even though the similarly named shell setup variable was removed.

Open the selected-report workflow in your fork and wait for completion.
Download `selected-report-<request-id>`.

The artifact includes HTML/PDF report and methods files, an analysis
bundle under `data/`, and provenance sidecars.
Keep the output folder intact when sharing it.

## 7. Troubleshooting

- Invalid repository: use `owner/repo`, not a URL.
- No successful source run: enable Actions and complete the update workflow.
- Missing/expired artifact: rerun the source workflow and verify its artifact.
- 401: check token validity and expiry.
- 403: check repository access, Actions write permission, policy, and rate limits.
- 404: check repository/token access and workflow availability.
- 422: check branch and workflow input values.
- Renderer rejects datasets: inspect eligibility and the workflow error;
  do not bypass validation.
- Different checkout and workflow behavior: remember the renderer checks out main.

Do not publish resolved Compose configuration or logs containing tokens.
Stop the UI with Ctrl+C. Clear the shell token when finished:

```bash
unset GITHUB_TOKEN
```

## End-to-end acceptance checklist

- UI displays the intended fork.
- Artifact lookup uses that fork and loads eligible datasets.
- A selected-report request starts a run in that same fork.
- The request uses the selected source run ID and canonical audience ID.
- The workflow succeeds and its artifact contains readable outputs.
- Provenance matches the request and source snapshot.
- No token appears in tracked files, reports, provenance, or shared logs.

Record actual results; mocked tests alone do not satisfy this checklist.

## Optional: watch and download an existing request

With GitHub CLI installed and authenticated, use the request ID shown
by the UI after a successful submission. This helper watches an existing
run; it does not create a new report request.

```bash
bash watch_and_open_report.sh REQUEST_ID "$GITHUB_REPOSITORY"
```

Replace REQUEST_ID with the actual request ID.
The default destination is `outputs/selected-reports/` relative to the script.
To choose a destination explicitly:

```bash
bash watch_and_open_report.sh REQUEST_ID "$GITHUB_REPOSITORY" "$HOME/Downloads/health-reports"
```

Set `REPORT_OPEN=0` to skip browser opening. If no usable opening tool is
available, the helper prints the downloaded HTML path. A failed browser
launch does not turn a successful download into a failed workflow.

Check usage without contacting GitHub:

```bash
bash watch_and_open_report.sh --help
```
