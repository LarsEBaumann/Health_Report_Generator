# Health reports: local setup and reproduction

Run commands from the repository root, containing `Snakefile`.
The version policy is recorded in `workflow/toolchain.json`.
The committed source data are under `data/reference/`, not `Data/`.

## 1. Clone and record the starting commit

```bash
git clone [https://github.com/LarsEBaumann/Health_Report_Generator.git](https://github.com/LarsEBaumann/Health_Report_Generator.git)
cd Health_Report_Generator
git rev-parse HEAD
git status --short --branch
```

For an existing checkout, preserve local changes before updating.
For comparison, use the same commit, data snapshot, and audience parameters.

## 2. Recommended setup: Docker

Prerequisites: Docker with a reachable daemon and Docker Compose.
The current report image targets Linux/amd64.
Native Windows and other CPU architectures have not been validated.

```bash
docker version
docker compose version
export LOCAL_UID="$(id -u)"
export LOCAL_GID="$(id -g)"
docker compose build report
```

Image creation requires internet access and may take several minutes:
it installs Python, R packages, Quarto, and pinned TinyTeX.
It does not replace your host R or TeX installation.

## 3. Generate all three audience reports

```bash
docker compose run --rm report snakemake --cores 2
```

No GitHub token, fork, or Actions workflow is required.
The pipeline reads committed reference data, archives the inputs,
validates and analyses them, and generates three audience outputs
from one shared report template using parameters.

The audiences are `researcher`, `health_institution`, and `public`.
For each audience, `results/reports/<id>/` contains:

- `report.html` and `methods.html`
- `report.pdf` and `methods.pdf`
- `provenance.json` and `provenance.pdf.json`
- Analysis tables and supporting records in `data/`
- A packaged Shiny application in `app/`

HTML pages embed machine-readable provenance.
`results/release.json` records output hashes and environment/code information.
`results/snapshots/` contains archived inputs.

Open HTML files using your browser or file manager.
Keep each audience folder intact when sharing it.

A successful build is not the same as deployment:
packaging Shiny does not start or publish a web application.

## 4. Verify the complete release

```bash
docker compose run --rm report python scripts/health_pipeline/check_outputs.py
docker compose run --rm report python scripts/health_pipeline/verify_release.py --out results
docker compose run --rm report Rscript tests/shiny_smoke.R results/reports/researcher/app
docker compose run --rm report Rscript tests/dashboard_smoke.R results/reports/researcher/app
docker compose run --rm report snakemake --dry-run --cores 1
```

All checks must succeed. An unchanged repeat build should report
`Nothing to be done`.

Also inspect each audience's HTML in a browser, test the table controls
and navigation/download links, and inspect PDFs for clipping.
Automated checks do not replace visual review.

Validation warnings and skipped checks are not equivalent to failures,
but must remain visible and be interpreted before publishing findings.
Do not bypass a failed validation gate.

## 5. Fresh-output reproduction

Use a new output directory rather than deleting an existing release:

```bash
docker compose run --rm report snakemake --cores 2 \
  --config out=reproduced/fresh-check
docker compose run --rm report python scripts/health_pipeline/check_outputs.py \
  --out reproduced/fresh-check
docker compose run --rm report python scripts/health_pipeline/verify_release.py \
  --out reproduced/fresh-check
```

For an archived-input rebuild, select an actual manifest created by
your successful build:

```bash
find results/snapshots -name manifest.json -print
```

Set the path to the intended manifest, then render to a new directory:

```bash
SNAPSHOT_MANIFEST='results/snapshots/<actual-snapshot-id>/manifest.json'
docker compose run --rm report snakemake --cores 2 \
  --config snapshot_manifest="$SNAPSHOT_MANIFEST" out=reproduced/archived
```

Replace the placeholder with a real path. If multiple snapshots exist,
choose the one matching the release you intend to reproduce.
Retain the code commit, configuration, lockfiles, and snapshot together.
Render timestamps and some document bytes may differ between runs;
do not claim byte-identical PDFs unless tested.

## 6. Alternative native pipeline environment

Install the declared R, Quarto, and TeX toolchain before native rendering.
Docker is the simpler route when those tools are unavailable.

Keep the report environment separate from the optional UI environment:
the pipeline lock pins pandas 2.2.3, while the current UI project requires
pandas >=3.0.6.

With uv installed, create a new pipeline environment:

```bash
uv venv --python 3.11.6 .venv-pipeline
uv pip install --python .venv-pipeline/bin/python \
  -r scripts/health_pipeline/requirements.lock.txt
Rscript workflow/restore_r.R
```

For pinned TinyTeX setup, inspect `scripts/ci/install_tinytex.sh` before
running it: it replaces `$HOME/.TinyTeX`.
To use it intentionally:

```bash
bash scripts/ci/install_tinytex.sh 2026.10
export PATH="$HOME/.TinyTeX/bin/x86_64-linux:$PATH"
```

Do not overwrite an existing environment or TeX installation without
first reviewing and preserving it.

Run with the pipeline interpreter explicitly:

```bash
.venv-pipeline/bin/python -m snakemake --cores 2
.venv-pipeline/bin/python -m pytest -q
```

Do not assume system Snakemake uses the activated virtual environment.

## 7. Partial targets for diagnosis

```bash
docker compose run --rm report snakemake tables --cores 2
docker compose run --rm report snakemake html --cores 2
docker compose run --rm report snakemake pdf --cores 2
docker compose run --rm report snakemake shiny --cores 2
```

Partial builds do not establish that a complete release works.

## 8. Data updates and optional interface

Local builds use the committed snapshot, not a live API request.
Remote API acquisition is implemented separately by the IDD data-update
workflow. A successful update can change the committed data and later findings.

The optional Marimo interface downloads a GitHub workflow artifact and
requests selected reports from a configured repository.
See `CONNECTOR_SETUP.md`; it is not required for local reporting.

## 9. Troubleshooting and evidence

- Docker connection/permission error: resolve daemon access before building.
- Download failure: retain the build log; do not disable TLS verification.
- Missing library/package: retain the exact error and dependency versions.
- Validation failure: inspect the checks; do not publish stale outputs as new.
- Broken links: keep the whole audience folder, including its data.
- Failed build: older files may remain; only a completed, verified release counts.

Record the OS, architecture, commit, image ID, runtime versions, parameters,
snapshot ID, exact commands, test results, and visual-review findings.
Do not include tokens in logs or provenance.
