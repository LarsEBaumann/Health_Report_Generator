# Health report: setup, testing, and demo guide

This repository turns the supplied disease surveillance data into a visual dashboard, a methods report, PDF reports, and a Shiny application. Run all commands from the repository root—the folder containing `Snakefile` and `README.md`.

## 1. Get the project

Clone the repository using its GitHub URL, then open a terminal in the cloned folder:

```bash
git clone YOUR_REPOSITORY_URL
cd Health_Report_Generator
```

Replace `YOUR_REPOSITORY_URL` with the actual URL. If you already cloned the repository, use `git pull` to get the latest changes after saving your own work. Teammates comparing results must use the same commit:

```bash
git rev-parse HEAD
```

The `Data/` folder is included in the repository. Generated outputs in `results/` are not included: you create them by running the workflow. Do not edit the raw data for the first test.

## 2. Install the prerequisites once

The commands below are for macOS or Linux. On Windows, use a WSL2/Linux terminal and install the prerequisites inside that environment. Native Windows has not been validated.

Install the versions recorded in `workflow/toolchain.json` before continuing: Python 3.11.6, R 4.3.2, and Quarto 1.3.353. Python patch releases from 3.11.6 up to, but not including, 3.12 are supported; CI validates 3.11.6. Use the recorded versions when comparing environments. Setup requires internet access; it may take several minutes.

Check that the tools are available:

```bash
python3.11 --version
Rscript --version
quarto --version
```

If any command is not found, install that tool or add it to your terminal's PATH before continuing. RStudio is optional; the workflow uses Rscript and Quarto directly.

Create a Python environment belonging to this repository and install the recorded dependencies:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r scripts/health_pipeline/requirements.lock.txt
Rscript workflow/restore_r.R
quarto install tinytex
```

The R restore command installs the recorded R packages, including ggplot2 and Shiny, into `.r-library/`. TinyTeX is needed for PDFs. Its actual version is recorded in release metadata because the installer is not byte-locked. Do not update dependency versions during the reproduction test.

Each time you open a new terminal, return to the repository folder and activate Python again:

```bash
source .venv/bin/activate
```

## 3. Build the complete project

```bash
snakemake --cores 2
```

Wait for the command to finish successfully. It archives the input data, harmonises it, checks quality, calculates the reporting tables, renders both reports, and packages Shiny. Do not present a build as successful if the command reports an error—even if older files exist in `results/`.

On Lavanya's Mac only, Quarto can instead be selected using its RStudio installation:

```bash
snakemake --cores 2 --config quarto=/Applications/RStudio.app/Contents/Resources/app/quarto/bin/quarto
```

Other laptops should use their own installed Quarto; do not copy this Mac-specific path.

### Where the outputs are

One build produces three audience reports from the same template; `<id>` is `researcher`, `health_institution` or `public` (see the README).

| Location | What it contains |
|---|---|
| `results/reports/<id>/report.html` | Main visual dashboard |
| `results/reports/<id>/methods.html` | Sources, methods, exclusions, and traceability |
| `results/reports/<id>/report.pdf` | Findings PDF |
| `results/reports/<id>/methods.pdf` | Methods PDF |
| `results/reports/<id>/data/` | Shared analysis tables and supporting records |
| `results/reports/<id>/app/` | Shiny app, Quarto sources, and their data |
| `results/reports/<id>/provenance.json` | Machine-readable provenance for the HTML (also embedded in each page); `provenance.pdf.json` for the PDF |
| `results/snapshots/` | Archived input files |
| `results/release.json` | Output fingerprints and recorded code/environment information |

Open `report.html` with your browser using Finder or your file manager. On macOS you can also run:

```bash
open results/reports/researcher/report.html
```

Keep the entire stakeholder output folder (`researcher`, `health_institution` or `public`) together when sharing reports so navigation and download links continue to work.

## 4. Test a fresh installation

Run these after a successful full build:

```bash
python -m pytest -q
Rscript tests/dashboard_smoke.R results/reports/researcher/app
Rscript tests/shiny_smoke.R results/reports/researcher/app
snakemake --dry-run --cores 2
```

Expected for the current code: all Python tests pass, both R checks pass, and the final command reports that nothing needs to be done. If you built with an explicit Quarto path, use the same `--config quarto=...` option for the dry run.

### Verify the numerical results against the current demo

This check applies to the supplied data and current stakeholder settings. Deliberately changing those inputs can change the expected fingerprints.

```bash
python - <<'PY'
from pathlib import Path
import hashlib

folder = Path('results/reports/researcher/data')
expected = {
    'metrics.csv': '4b80640609dff31f79fd977774cd91a8c8768d3a7ab551eada0e7f8e8799def2',
    'series.csv': '58ce7f3b40237c7d0f37529430bb228d4f35de6eb731793883a41c738953168f',
}
for name, target in expected.items():
    actual = hashlib.sha256((folder / name).read_bytes()).hexdigest()
    assert actual == target, f'Results differ: {name}'
    print(f'PASS: {name} matches the demo exactly')
PY
```

Both lines should say PASS. PDF bytes may differ between rendering environments; matching PDF file hashes is not required.

Also inspect the HTML charts, expand the supporting table, follow Methods & sources, and open both PDFs to check for clipping. Launch Shiny as described below and change the selected disease.

For each laptop, record the operating system, commit ID, Python/R/Quarto versions, test results, build result, CSV comparison result, and any visual problems. Save the complete error output if something fails. A configured GitHub Actions workflow also tests and builds on Linux when enabled; check its actual result rather than assuming it passed.

## 5. Demo preparation

Do this before the presentation, not during it:

1. Finish the full build and checks above.
2. Open `report.html` and `methods.html` in browser tabs.
3. Open `report.pdf` as a backup.
4. Start Shiny from the repository root:

```bash
Rscript -e 'shiny::runApp("results/reports/researcher/app", launch.browser=TRUE)'
```

Keep that terminal running. If a browser does not open, copy the local address printed after `Listening on` into your browser. Press Control+C in the terminal when you want to stop the app.

### Suggested three-minute walkthrough

| Time | Show | Explain |
|---|---|---|
| 0:00–0:30 | Dashboard title and snapshot ID | “This report uses a specific archived input release. We can identify the data behind it.” |
| 0:30–1:15 | Summary cards and group charts | “These are reported case notifications compared with 2019. The separate view without influenza shows how group composition affects the viral comparison.” |
| 1:15–1:45 | Disease comparison and supporting table | “We can move from the overall pattern to individual diseases and inspect the numbers.” |
| 1:45–2:15 | Methods & sources | “Selection decisions, exclusions, data quality, and source records are available separately from the findings.” |
| 2:15–2:45 | Shiny: Explore a disease | “The interactive app uses the same prepared data as the reports.” Change the selected disease. |
| 2:45–3:00 | PDF and workflow explanation | “One workflow produces shared analysis tables, HTML/PDF reports, and a Shiny app. Teammates can rebuild and compare the numerical results.” |

Use “reported notifications,” not “all infections.” A rise in notifications is descriptive and does not by itself establish its cause. In the percentage-change chart, 0% means the same as 2019 and +100% means twice the 2019 value. The default report covers the configured CHFL geography (Switzerland and Liechtenstein).

Do not claim live updates: this workflow uses the supplied local data. Remote API acquisition has not been implemented. Shiny runs locally; building it does not deploy a public website.

## 6. Useful commands after setup

```bash
# Only build the analysis tables
snakemake tables --cores 2

# Only build the HTML reports and their required inputs
snakemake html --cores 2

# Only build the PDFs and their required inputs
snakemake pdf --cores 2

# Prepare the Shiny app and its required inputs
snakemake shiny --cores 2
```

A partial target is useful for diagnosis, but does not confirm that the complete release builds. Running `snakemake` again without changes normally does no work; this is expected.

## 7. Rebuild the exact archived demo inputs

After your first build, the supplied data should have created the following archive. To rebuild from it into a separate folder:

```bash
snakemake --cores 2 --config \
  snapshot_manifest=results/snapshots/f1484622df74831453d66fb36cfc9fab002bd0695385195143930328d4f74653/manifest.json \
  out=reproduced
```

Outputs are now under `reproduced/`. This uses archived inputs rather than rereading `Data/`. It still uses the current code and settings, so keep their versions with the archive for long-term reproduction. If this archive is missing, do not invent a manifest: complete the initial build or obtain the original archive from the team.

## 8. Troubleshooting

| Problem | What to do |
|---|---|
| `snakemake: command not found` | Activate `.venv`; confirm dependency installation completed. |
| `Rscript` or `quarto` not found | Install the missing tool or fix PATH. Reopen the terminal and check its version. |
| Missing R package / ggplot2 | Run `Rscript workflow/restore_r.R` from the repository root. |
| PDF fails with a TeX error | Confirm TinyTeX is installed. Read the missing-package/error details; the report does not automatically install TeX packages during rendering. You can diagnose HTML separately with `snakemake html --cores 2`. |
| Validation fails | Read the reported failure and `results/checks.csv` if it was produced. Do not bypass validation to publish the report. |
| CSV fingerprints differ | Compare commit IDs, data, and stakeholder settings. Preserve the output and error for investigation. |
| HTML links or downloads fail | Keep the entire stakeholder output folder together, including `data/`. |
| Shiny stops responding | Check that its terminal is still running and inspect that terminal for errors. Restart the launch command if needed. |
| Installation fails on another laptop | Record the OS, tool versions, failed command, and full error. Cross-laptop support is verified by these tests, not assumed. |

For the demo, use the already verified HTML/PDF if a live app fails. Clearly distinguish a presentation fallback from a newly successful build.
