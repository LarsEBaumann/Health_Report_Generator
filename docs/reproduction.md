# Reproduction guide

How to set up the toolchain, build all audience reports, and reproduce an archived release exactly. The README has the short version; this is the full detail.

## Setup and run

Run commands from the repository root. The version policy is recorded in
`workflow/toolchain.json`: Python 3.11.6, R 4.3.2, Quarto 1.3.353,
uv 0.8.14, and checksum-pinned TinyTeX v2026.10.

### Recommended: Docker

The current report image targets Linux/amd64. Docker and Docker Compose
must be installed, and the Docker daemon must be reachable.

```sh
export LOCAL_UID="$(id -u)"
export LOCAL_GID="$(id -g)"
docker compose build report
docker compose run --rm report snakemake --cores 2
```

Image creation downloads software and restores packages.
The report command reads committed reference data and requires no GitHub
token, fork, or GitHub Actions. It does not perform an IDD data update.

`Dockerfile.report` provides the report environment.
The original `Dockerfile` provides the separate optional UI environment.

### Alternative: native setup

Install the declared R and Quarto versions and required TeX toolchain.
Use a separate pipeline environment, not the optional UI's `.venv`:
the two current dependency specifications require incompatible pandas versions.

With uv installed:

```sh
uv venv --python 3.11.6 .venv-pipeline
uv pip install --python .venv-pipeline/bin/python \
  -r scripts/health_pipeline/requirements.lock.txt
Rscript workflow/restore_r.R
```

Inspect `scripts/ci/install_tinytex.sh` before running it:
it replaces `$HOME/.TinyTeX`. To intentionally install the pinned bundle:

```sh
bash scripts/ci/install_tinytex.sh 2026.10
export PATH="$HOME/.TinyTeX/bin/x86_64-linux:$PATH"
.venv-pipeline/bin/python -m snakemake --cores 2
```

The installer verifies the archive digest and required KOMA-Script class.
Quarto's automatic TeX package installation is disabled in the template.

### Targets and wrapper

For Docker, replace the final command with any partial target:

```sh
docker compose run --rm report snakemake tables --cores 2
docker compose run --rm report snakemake html --cores 2
docker compose run --rm report snakemake pdf --cores 2
docker compose run --rm report snakemake shiny --cores 2
```

Partial targets do not establish that a complete release works.

The native wrapper
`bash scripts/health_pipeline/run_all.sh [data_root] [out_dir] [extra snakemake args]`
runs Snakemake from PATH. Activate `.venv-pipeline` before using it:

```sh
source .venv-pipeline/bin/activate
bash scripts/health_pipeline/run_all.sh
```

Set `QUARTO` to override the renderer path and `CORES` to change parallelism.
See GETTING_STARTED.md for complete output and verification instructions.

## Reproduce a specific archived release

```sh
snakemake --cores 2 --config \
  snapshot_manifest=results/snapshots/REPLACE_WITH_SNAPSHOT_ID/manifest.json \
  out=reproduced
```

This mode verifies and reads only that archived snapshot, without requiring the live `data/reference/` tree or any API. Retain the snapshot **and** code/config/environment versions with the report. Hashes cannot recover deleted data. Paths inside a snapshot and its lineage are relative, so the archive can move between computers. Original source record numbers count CSV records (header = 1), not physical lines in multiline CSV fields.

For an update, place a new release in `data/reference/` and run the ordinary workflow. It creates a new content-addressed archive rather than replacing the old snapshot. Building never contacts the network. Acquisition from the public IDD API is a separate step: `src/sync_idd_exports.py` (run weekly by `.github/workflows/update-lyme-data.yml`, or manually) downloads each export into `data/reference/<DATASET>/` together with a `retrieval.json` recording the source URLs, retrieval time and hashes; changes are committed so every release is a reviewable change to `data/reference/`.

## Verify a build

```sh
python scripts/health_pipeline/check_outputs.py
Rscript tests/shiny_smoke.R results/reports/researcher/app
python -m pytest -q
```

`check_outputs.py` confirms exactly one HTML report per configured audience, embedded and sidecar provenance, and distinct presentations. Compare `results/release.json` (artifact and code hashes, Git state, runtime versions) with the one you expect.
