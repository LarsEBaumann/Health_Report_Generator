# How to run this — step by step

Everything goes through one script, `run.py`. The same commands work on Windows, Linux and
macOS.

```sh
python run.py              # 1. build the two full reports (nothing opens)
python run.py web          # 2. report builder page: pick diseases, build locally
python run.py test         # 3. run the tests
python run.py release      # 4. full three-audience release (needs Docker)
python run.py clean        # 5. delete everything the build produced
python run.py app          #    Marimo interface (GitHub request flow, optional)
```

If you only want to see the reports, you need **step 0 and step 1**. Nothing else.

---

## Step 0 — install the two prerequisites

| Tool | Needed for | Install |
|---|---|---|
| **uv** | everything | <https://docs.astral.sh/uv/getting-started/installation/> |
| **Quarto** | the reports | <https://quarto.org/docs/get-started/> |
| Docker | only `run.py release` | <https://docs.docker.com/get-started/> |

Check they are there:

```sh
uv --version
quarto --version
```

You do **not** need to install Python yourself, and there is **no setup step**: `uv` fetches
Python 3.11 and builds the single environment in `.venv/` the first time you run anything.
Nothing to activate.

The exact versions this project is validated against are declared in
`workflow/toolchain.json`; the container in `Dockerfile` installs the same ones.

---

## Step 1 — build and open the reports

```sh
python run.py
```

What happens, in order:

1. `uv` creates `.venv/` and installs the locked dependencies *(first run only, ~2 min)*
2. The pipeline archives the 56 datasets in `data/reference/` with checksums
3. It merges them into one cleaned table and runs the quality checks
4. Quarto renders the two reports
5. Your browser opens the landing page

Expect **3–5 minutes the first time**, and a few seconds afterwards if nothing changed.
You will see `8 of 8 steps (100%) done` followed by `Done: .../results/site/index.html`.

**Nothing opens a browser by itself.** Add `--open` if you want it to, or read the reports
inside the explorer (step 2), which shows each report with its provenance record.

### Opening the reports

The landing page opens by itself. To open it again later, no command needed — it is a
plain file on disk:

| Report | File | Answers |
|---|---|---|
| **Landing page** | `results/site/index.html` | pick one of the two below |
| Public health officials | `results/site/public_health.html` | What needs attention now, and where? |
| Researchers | `results/site/researcher.html` | How was it measured, and can I reproduce it? |

Add `--open` to have the build open it for you. Otherwise double-click the file, or:

```sh
start results/site/index.html     # Windows
open  results/site/index.html     # macOS
xdg-open results/site/index.html  # Linux
```

Or open the report inside the explorer, which also shows its provenance record:
`python run.py web`.

Each report is a **single self-contained file** — no server and no internet needed, so you
can email one or put it on a USB stick and it still works, charts included. At the bottom
of each is a Provenance section recording the source checksums, the data snapshot id, the
code version, the tool versions and the retrieval dates, with the full record downloadable
as JSON.

### Adding a third report

Add `reports/<name>.qmd` and list `<name>` under `quarto_reports` in
[workflow/config.yaml](workflow/config.yaml). The HTML under `results/` is a build artifact
and is never edited by hand.

---

## Step 2 — explore the data and build a report

```sh
python run.py web
```

Opens the **Infection Data Explorer** on <http://127.0.0.1:2718>.

**Start page** — pick an audience: Researcher, Health institution or General public. Each
card shows that audience's own question from its configuration file.

**Dashboards** — four tabs per audience, with a filter bar for pathogen class and year:

| Tab | Shows |
|---|---|
| Overview | Key figures, reported cases by pathogen class |
| Trends | Index against the reference year, each disease over time |
| Changes | Change per disease vs the reference and previous year, datasets left out |
| Quality & sources | All quality checks, provenance, and the audience's report parameters |

Which panels appear is **not hard-coded**: it is the `outputs` list in
`backend/config/stakeholders/<id>.json`. Change that file and the dashboards follow.

Every figure comes from the committed FOPH snapshot in this repository — 12 diseases,
2019 and 2021–2025, 56 datasets, 853 quality checks. Nothing on the page is synthetic or
estimated. **Save this dashboard** writes the panels you are looking at to one
self-contained HTML file.

**Full report tab** — two things live here:

- **Build one**: tick the diseases you want and press **Generate report**. It renders with
  Quarto on this machine, takes roughly 20–60 seconds, and is kept in
  `results/site/selected/`.
- **Read one**: pick any report, full or built from a selection, and it opens **inside the
  page** at its full detail, exactly as the file itself looks. Underneath it sits the
  report's own provenance record — publisher dates, retrieval dates, the cleaned input's
  SHA-256, the code hashes, the tool versions, the Git commit, and the 56 datasets behind
  it. **Taller** expands the reader; **Open in a new tab** and **Download** do what they say.

There is no PDF on this path: PDFs come from the R toolchain in `python run.py release`.
The HTML report carries the same content.

Researcher and Health institution build locally. **General public** uses the R template, so
the page says so and points you at `python run.py release`.

The page loads no fonts, scripts or styles from the internet, so it works entirely offline.

### Optional: the Marimo interface and GitHub Actions

```sh
python run.py app
```

`frontend/ui.py` is the original interface. It prefers the same local build, so it also
works with no GitHub configuration. Without a local build it falls back to its original
behaviour: download a data bundle from a GitHub repository and ask that repository's
Actions to render. That needs your own fork, Actions enabled, and a token:

```sh
# Windows PowerShell
$env:GITHUB_REPOSITORY = "YOUR_OWNER/YOUR_FORK"
$env:GITHUB_TOKEN      = "<fine-grained PAT, Actions read/write>"

# Linux / macOS
export GITHUB_REPOSITORY="YOUR_OWNER/YOUR_FORK"
export GITHUB_TOKEN="<fine-grained PAT, Actions read/write>"
```

That route exists because the three-audience R reports need R, TeX and Shiny, which the
Actions runner has pre-installed. Full instructions are in
[CONNECTOR_SETUP.md](CONNECTOR_SETUP.md).

---

## Step 3 — run the tests

```sh
python run.py test
```

Expect **113 passed**. Anything else is a real failure worth looking at.

---

## Step 4 — the full three-audience release

```sh
python run.py release
```

This builds the researcher, health-institution and public reports with PDFs, Shiny app
packages and a `results/release.json` recording every artifact hash.

It needs **R and TeX** on top of step 0, so it runs in Docker — the image in `Dockerfile`
carries Python, R, Quarto and TinyTeX together. Without Docker the command falls back to a
native build and tells you what is missing.

Outputs land in `results/reports/<audience>/`. Keep each of those folders intact, or the
links and downloads inside the reports break.

---

## Step 5 — clean up

```sh
python run.py clean
```

Removes `results/` (~287 MB) and `.snakemake/`. Both are rebuilt by step 1.

Also deletable by hand, all git-ignored and all regenerated automatically:

| Path | Size | Comes back with |
|---|---|---|
| `.venv/` | 530 MB | any `python run.py` |
| `.pytest_cache/`, `.ruff_cache/` | small | next test or lint run |
| `backend/__pycache__/` and friends | small | next Python run |

**Never delete `data/reference/`.** It is the committed source snapshot, not a build
artifact — the reports are reproduced against it, and it cannot be regenerated without
re-downloading different data from the FOPH API.

---

## If something breaks

| Symptom | What it means |
|---|---|
| `Missing: uv` or `Missing: quarto` | Step 0 is incomplete; install from the link the message prints |
| `No such file or directory: 'Rscript'` | R is only needed for step 4; step 1 never uses it |
| `Nothing to be done` | Already built and up to date. Run `python run.py clean` first to force a rebuild. |
| The browser did not open | The build still worked — open `results/site/index.html` yourself |
| Web interface shows a repository-configuration error | Expected without a fork and token; see step 2 |
| Port 2718 already in use | `python run.py web --port 8080` |
| A build step fails on quality checks | Intended: the gate stops reports being built on data that failed `checks.csv` |

---

## Where things are

| Path | What |
|---|---|
| `run.py` | The entry point for everything above |
| `Snakefile`, `workflow/` | The workflow and its configuration |
| `backend/` | The Python pipeline: ingest, harmonise, check, analyse, render |
| `reports/` | Report sources: `<name>.qmd` plus `shared/` helpers and `assets/` |
| `frontend/web/` | The explorer page: `app.py` (API), `data.py` (aggregation), `page.html` |
| `frontend/` | `local_build.py` (local rendering), `ui.py` (Marimo) and GitHub helpers |
| `data/reference/` | The committed source-data snapshot, one folder per dataset |
| `results/` | Everything the build produces (git-ignored) |
| `tests/` | The suite behind step 3 |

One warning about the data: `frontend/sync_idd_exports.py` ignores its arguments, calls the
FOPH API immediately and **overwrites `data/reference/`**, which replaces the committed
snapshot the reports are reproduced against. You never need it for any step above; CI runs
it on a schedule. If you run it by accident: `git checkout -- data/reference`.

More depth: [README.md](README.md) for the project and its outputs, and
[CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow.
