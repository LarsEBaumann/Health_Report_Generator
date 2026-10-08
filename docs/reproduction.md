# Reproduction guide

How to set up the toolchain, build all audience reports, and reproduce an archived release exactly. The README has the short version; this is the full detail.

## Setup and run

The fastest path is `bash scripts/health_pipeline/run_all.sh`, which runs the same `snakemake --cores 2` described here.

Run commands from the repository root. The supported and validated toolchain is recorded in `workflow/toolchain.json`: Python 3.11.6 (supported range `>=3.11.6,<3.12`), R 4.3.2, Quarto 1.3.353, and uv 0.8.14. CI, Conda metadata, Docker, and project metadata are checked against this contract.

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r scripts/health_pipeline/requirements.lock.txt
Rscript workflow/restore_r.R
```

Install Quarto **1.3.353**. CI installs the checksum-pinned full **TinyTeX v2026.10** bundle through `scripts/ci/install_tinytex.sh`; local PDF builds require an equivalent TeX installation. The installer verifies the archive digest and the required KOMA-Script class before rendering. Place `quarto` on PATH, or supply its path below. These are explicit installation steps; ordinary builds never fetch new data or install packages deliberately. Quarto's automatic TeX package installation is disabled in the template so PDF builds fail clearly if their TeX environment is incomplete.

```sh
snakemake --cores 2
# On this Mac, when Quarto is bundled with RStudio:
snakemake --cores 2 --config quarto=/Applications/RStudio.app/Contents/Resources/app/quarto/bin/quarto
```

Optional targets: `snakemake tables --cores 1`, `snakemake html --cores 1`, `snakemake pdf --cores 1`, `snakemake shiny --cores 1`.

`bash scripts/health_pipeline/run_all.sh [data_root] [out_dir] [extra snakemake args]` is a thin wrapper around `snakemake --cores ${CORES:-2}` (defaults from `workflow/config.yaml`). Set `QUARTO` to override the renderer path and `CORES` to change parallelism. The former Python-generated HTML is replaced by the shared QMD to avoid duplicate statistical logic.

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
