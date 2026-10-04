# Connector setup

The connector app reads a **versioned lineage artifact**. It does not read `data/reference` directly. The artifact is created by the **Update IDD reference data and build report artifact** GitHub Actions workflow.

## 1. Get a lineage artifact

Run the update workflow on the `connector` branch in GitHub Actions. When it succeeds, note its numeric run ID. Then download the artifact locally with GitHub CLI:

```bash
gh auth login
export LINEAGE_RUN_ID=REPLACE_WITH_SUCCESSFUL_RUN_ID
rm -rf data/lineage
mkdir -p data/lineage
gh run download "$LINEAGE_RUN_ID" --repo LarsEBaumann/Health_Report_Generator \
  --name "health-report-$LINEAGE_RUN_ID" --dir data/lineage
find data/lineage -name harmonised.parquet -print
```

The final command must print exactly one `harmonised.parquet` path.

## 2. Allow report requests

Create a fine-grained GitHub personal access token that can access this repository and has **Actions: read and write** permission. Do not add it to Git, a notebook, or a compose file. Export it only in the current shell:

```bash
read -rsp 'GitHub token: ' GITHUB_TOKEN; echo
export GITHUB_TOKEN
export GITHUB_REPOSITORY=LarsEBaumann/Health_Report_Generator
```

## 3. Start the UI

```bash
cd ~/projects/Health_Report_Generator
git switch connector
git pull --ff-only origin connector

LOCAL_UID="$(id -u)" LOCAL_GID="$(id -g)" \
LINEAGE_RUN_ID="$LINEAGE_RUN_ID" \
GITHUB_TOKEN="$GITHUB_TOKEN" \
GITHUB_REPOSITORY="$GITHUB_REPOSITORY" \
docker compose run --rm -p 127.0.0.1:2718:2718 report \
sh -lc 'mkdir -p /tmp/report-home/.config /tmp/report-home/.cache /tmp/report-home/.local/share &&
export HOME=/tmp/report-home XDG_CONFIG_HOME=/tmp/report-home/.config XDG_CACHE_HOME=/tmp/report-home/.cache XDG_DATA_HOME=/tmp/report-home/.local/share &&
uv sync --locked &&
uv run marimo run src/ui.py --host 0.0.0.0 --port 2718 --show-tracebacks'
```

Open `http://127.0.0.1:2718`. Keep the terminal running.

## 4. Retrieve the result

After **Generate report**, open the `Render selected stakeholder report` workflow in GitHub Actions. Download its `selected-report-<request-id>` artifact. It contains:

- `report.html`
- `provenance.json`
- `data/`, the analysis bundle used to render the report

## Troubleshooting

- **No downloaded lineage artifact**: repeat step 1 and confirm `data/lineage` contains `harmonised.parquet`.
- **Set GITHUB_TOKEN and LINEAGE_RUN_ID**: export both variables in the same shell that starts Docker.
- **401/403 from GitHub**: re-create the fine-grained token with access to this repository and Actions read/write permission.
- **No report generated**: open the Actions run log; the report deliberately fails if the selected data do not contain at least one eligible viral and one eligible bacterial series.
