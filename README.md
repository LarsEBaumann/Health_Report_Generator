# Health Report Generator

This project turns one checked snapshot of Swiss infectious-disease data into
reports for three audiences:

- **Researcher** — a detailed report with source tables and provenance.
- **Health institution** — a monitoring report for public-health work.
- **General public** — a plain-language report.

A report request records the audience and selected datasets. Snakemake then
prepares the data, applies checks, creates the selected analysis tables, and
renders HTML and PDF reports. Every formal report includes provenance: the data
snapshot, filters, checksums, software environment, and render time.

This branch also includes two local interfaces that can start a report request
through GitHub Actions and display the completed HTML report.

## Before you start

You need:

1. Git.
2. Docker Desktop, open and running.
3. Python 3.10 or later, only to start the Docker release command.
4. For the local interfaces only: a GitHub fine-grained access token with
   **Actions: Read and write** permission for the repository you will use.

The full release runs Python, R, Quarto, TinyTeX and Snakemake inside Docker.
You do not need to install those tools on your computer for that route.

## First test: build every report locally

### 1. Clone the repository

If you are testing the shared repository:

```sh
git clone https://github.com/LarsEBaumann/Health_Report_Generator.git
cd Health_Report_Generator
git checkout integration/marimo-reporting
```

If you are testing your own fork, replace `YOUR-ACCOUNT` below. Your fork must
contain the `integration/marimo-reporting` branch.

```sh
git clone https://github.com/YOUR-ACCOUNT/Health_Report_Generator.git
cd Health_Report_Generator
git checkout integration/marimo-reporting
```

### 2. Confirm Docker is running

```sh
docker --version
docker compose version
```

If either command fails, open Docker Desktop, wait until the engine is running,
and try again.

### 3. Run the complete release

From the repository root:

```sh
export LOCAL_UID="$(id -u)"
export LOCAL_GID="$(id -g)"
python3 run.py release --cores 2
```

The first run builds the Docker image and can take several minutes. Later runs
reuse the image unless its dependencies change.

A successful run writes results to `results/`:

```text
results/reports/public_health_expert/                 legacy report and Shiny bundle
results/requests/full-release-researcher-*/           researcher HTML and PDF
results/requests/full-release-health_institution-*/   health-institution HTML and PDF
results/requests/full-release-public-*/               public HTML and PDF
results/checks.csv                                    data-quality checks
results/release.json                                  release metadata
results/snapshots/<snapshot-id>/manifest.json         source snapshot record
```

Open an HTML report in your browser, for example:

```sh
open results/requests/full-release-public-*/report.html
```

On Linux, use your file manager or `xdg-open` instead of `open`.

## Test a selected report through GitHub Actions

This route is used by both local interfaces. It is useful when a person chooses
one audience and one or more datasets.

### 1. Set your repository values

From `marimo-ui/`, run the following. Replace the values in capitals with the
repository and branch you are testing.

```sh
cd marimo-ui

export GITHUB_REPOSITORY='YOUR-ACCOUNT/Health_Report_Generator'
export GITHUB_APP_REF='integration/marimo-reporting'
export GITHUB_BRANCH='integration/marimo-reporting'
export GITHUB_WORKFLOW='validate.yml'
export GITHUB_REQUEST_WORKFLOW='request-report.yml'
```

What each setting means:

| Variable | What to enter |
|---|---|
| `GITHUB_REPOSITORY` | `owner/repository`, for example `LarsEBaumann/Health_Report_Generator` or your fork. |
| `GITHUB_APP_REF` | The branch that contains `request-report.yml`; use `integration/marimo-reporting` for this branch. |
| `GITHUB_BRANCH` | The branch containing a successful `validate.yml` run and its data artifact; normally the same branch. |
| `GITHUB_WORKFLOW` | `validate.yml`. Do not change it unless the validation workflow has been renamed. |
| `GITHUB_REQUEST_WORKFLOW` | `request-report.yml`. Do not change it unless the request workflow has been renamed. |

For the shared repository, the first line is:

```sh
export GITHUB_REPOSITORY='LarsEBaumann/Health_Report_Generator'
```

### 2. Add your GitHub token to this Terminal session

Create a **fine-grained personal access token** in GitHub with access to the
repository and **Actions: Read and write** permission. Paste it privately when
prompted:

```sh
printf 'GitHub token: '
stty -echo
IFS= read -r GITHUB_TOKEN
stty echo
printf '\n'
export GITHUB_TOKEN
```

The token will not appear while you type. Do not put it in a file, commit it,
or paste it into chat.

### 3. Make sure validation data are available

The interfaces read the newest successful artifact from `validate.yml` before
they show dataset choices.

In GitHub, open **Actions** and check for a successful **Validate and build
reports** run on `integration/marimo-reporting`. If there is none, run that
workflow first and wait for it to finish.

## Run the compact Marimo form

Keep the environment variables and token from the previous section in the same
Terminal window. From `marimo-ui/`:

```sh
docker compose --profile ui run --rm \
  -p 127.0.0.1:2718:2718 \
  -p 127.0.0.1:2720:8000 ui \
  sh -lc 'mkdir -p /tmp/report-home/.config /tmp/report-home/.cache /tmp/report-home/.local/share /app/.cache/github-artifact/requested-reports &&
  (python -m http.server 8000 --directory /app/.cache/github-artifact/requested-reports >/tmp/report-static.log 2>&1 &) &&
  export HOME=/tmp/report-home XDG_CONFIG_HOME=/tmp/report-home/.config XDG_CACHE_HOME=/tmp/report-home/.cache XDG_DATA_HOME=/tmp/report-home/.local/share &&
  uv sync --locked &&
  uv run marimo run src/ui.py --host 0.0.0.0 --port 2718 --show-tracebacks'
```

Open [http://127.0.0.1:2718](http://127.0.0.1:2718).

Choose an audience, choose one or more diseases, then select **Generate
report**. The interface starts a GitHub Actions run, waits for it to finish,
downloads the matching artifact, and shows the report.

## Run Infection Data Explorer

Use a second Terminal window. Set the same variables and token again, then run:

```sh
cd /path/to/Health_Report_Generator/marimo-ui

docker compose --profile explorer run --rm \
  -p 127.0.0.1:2721:2718 explorer
```

Open [http://127.0.0.1:2721](http://127.0.0.1:2721).

The Explorer provides audience cards, data overview pages, disease selection,
and an embedded report after GitHub Actions has completed.

The message printed in the Terminal may say port `2718`. That is the port
inside Docker. In your browser, use `2721` because it is the port mapped on
your computer.

### If a port is already in use

Stop the existing service with `Ctrl+C`, or choose another host port. For
example:

```sh
docker compose --profile explorer run --rm \
  -p 127.0.0.1:2722:2718 explorer
```

Then open [http://127.0.0.1:2722](http://127.0.0.1:2722).

## What happens after a request

1. The interface sends a validated request to GitHub Actions.
2. The Action checks the request and finds the checked source snapshot.
3. It restores prepared data from cache when the snapshot and environment
   match. Otherwise it prepares the data once and saves the checked cache.
4. Snakemake analyses only the selected datasets.
5. Quarto renders HTML and PDF outputs.
6. GitHub Actions uploads a `requested-health-report-<run-id>` artifact.
7. The local interface downloads that artifact and displays its HTML report.

The first request for a snapshot can take longer because data preparation is
needed. A later request with a different audience or disease selection can
reuse the prepared data, but it still creates a fresh analysis and report.

## Check that a test worked

For either interface:

1. Choose an audience and at least one disease.
2. Confirm that a new **Build requested health report** run appears in GitHub
   Actions.
3. Wait for the run to show a green tick.
4. Confirm that the HTML report opens in the interface.
5. Open the HTML report in a separate browser tab and download the PDF.
6. Check that the report names the audience and datasets you chose.
7. Open the report provenance or `result.json` in the artifact and confirm it
   records the request ID, snapshot, filters, checksums, and render time.

## Important limits

- The current request workflow supports the infectious-disease data structure
  included in this repository. It is not yet a general analyser for any CSV.
- The current local disease pickers show included viral and bacterial datasets.
  Other source types need a reviewed adapter before they can be selected and
  reported as case trends.
- A selected report is descriptive. It does not make causal claims or estimate
  all infections.
- The Shiny app is part of the legacy full release. It is not yet generated for
  every selected request.
- GitHub Actions artifacts are retained for 30 days. Download formal outputs
  and supporting files if they must be retained longer.

## Troubleshooting

| Problem | What to check |
|---|---|
| `docker: command not found` | Install Docker Desktop, open it, then restart Terminal. |
| Port already allocated | Stop the old container or choose a different host port as shown above. |
| The interface says it cannot load report data | Confirm `GITHUB_REPOSITORY`, `GITHUB_BRANCH`, token permissions, and a successful `validate.yml` artifact. |
| GitHub rejects the request | Confirm `GITHUB_APP_REF` names a branch containing `request-report.yml`, and that Actions are enabled. |
| A fork fails to read the request image | Confirm that the fork can read the pinned GitHub Container Registry image used by `request-report.yml`. |
| The report request is slow | Check the Action log. The first request may be preparing data; later matching requests should report a cache hit. |
| The report does not appear after an Action succeeds | Open the matching Action artifact and look for `result.json` and `report.html`. |

## Further documentation

- [GETTING_STARTED.md](GETTING_STARTED.md) — native environment and detailed reproduction checks.
- [REQUEST_WORKFLOW.md](REQUEST_WORKFLOW.md) — request JSON schema, selection rules, and output structure.
- [marimo-ui/README.md](marimo-ui/README.md) — short reference for the two local interfaces.
- [REQUEST_IMAGE.md](REQUEST_IMAGE.md) — locked Docker request environment and its tests.
