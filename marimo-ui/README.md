# Local user interfaces

This folder provides two local front ends for the same request-driven report
workflow. Both read the validated data artifact, dispatch
`.github/workflows/request-report.yml` with a validated request, wait for the
matching GitHub Actions run, and display the resulting report artifact locally.
They do not contain analytical logic or a GitHub token in source code.

- **Marimo form**: a compact direct form for choosing an audience and diseases.
- **Infection Data Explorer**: a visual explorer with audience cards, dashboards,
  disease selection and an embedded generated report.

## One-time requirements

- Docker Desktop is running.
- A GitHub fine-grained token has **Actions: Read and write** access to this
  repository. Keep it in your shell session only; never commit it.
- The selected GitHub branch contains `validate.yml` and `request-report.yml`.

From this folder, configure the repository once per Terminal session:

```sh
export GITHUB_REPOSITORY='OWNER/REPOSITORY'
export GITHUB_APP_REF='BRANCH_WITH_THE_WORKFLOWS'
export GITHUB_BRANCH='BRANCH_WITH_THE_VALIDATED_DATA'
export GITHUB_WORKFLOW='validate.yml'
export GITHUB_REQUEST_WORKFLOW='request-report.yml'

printf 'GitHub token: '
stty -echo
IFS= read -r GITHUB_TOKEN
stty echo
printf '\n'
export GITHUB_TOKEN
```

## Run both interfaces

Use two Terminal windows, each configured as above.

### 1. Marimo form — port 2718

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

Open `http://127.0.0.1:2718`.

### 2. Infection Data Explorer — port 2721

```sh
docker compose --profile explorer run --rm \
  -p 127.0.0.1:2721:2718 explorer
```

Open `http://127.0.0.1:2721`. The message printed by Docker shows port `2718`
inside the container; the browser must use `2721`, which is the mapped port on
your computer.

If a port is occupied, either stop the existing service with `Ctrl+C` in its
Terminal or replace the number before the colon, for example
`-p 127.0.0.1:2722:2718`, then open port `2722`.

## Acceptance check

For each interface, choose an audience and one or more diseases. Confirm that:

1. a new request appears in GitHub Actions;
2. the matching HTML report displays locally after the Action succeeds;
3. the HTML opens separately and the PDF downloads when requested; and
4. the report metadata identifies the selected audience and datasets.
