# SourcePRISM web integration baseline

Recorded: 2026-10-11

## Repository

- Upstream: LarsEBaumann/Health_Report_Generator
- Fork: SourcePRISM/Health_Report_Generator
- Fork visibility: public
- Development branch: feat/web-integration
- Baseline commit: 6cbe68ba3eb7dc7198b229a13992638e83d5a315

## Local environment

- Ubuntu 26.04.1 LTS, x86_64
- Docker 29.8.1
- Docker Compose v5.5.1
- Approximately 7.7 GiB total RAM

## Existing audience release

- Report image build succeeded using cached dependency layers.
- Snakemake found existing outputs up to date; no fresh audience render ran.
- No-work invocation elapsed time: 5.415 seconds.
- Audience outputs and provenance verification passed.
- Release hashes, provenance and rendered-link verification passed.
- Final dry run required no work.
- Existing results directory size: 333 MB.
- Working tree remained clean.

## Custom-report experiment

Request: examples/request-2022-2025.json

Local experiment directory: results/web-baseline-pWPGNS

- Dedicated fresh cache: first invocation reported cache miss.
- First invocation elapsed time: 36.177 seconds.
- Second identical invocation reported cache hit.
- Second invocation elapsed time: 3.137 seconds.
- Recursive comparison found identical output contents.
- report.html, methods.html, provenance.json and
  request_provenance.json were present and non-empty.
- Each output directory occupied approximately 2.2 MB.
- Dedicated cache occupied approximately 51 MB.
- Working tree remained clean.

Cache key:
0908c378fa73c0b7bb02b441dfc5902570cf728808293e2e3a578fd1bf765484

## Interpretation and outstanding checks

Timings include Docker Compose/container startup.
They describe one request on one host, not a capacity guarantee.
The fresh-cache experiment does not imply cold OS or image caches.

Not yet established:
- Full fresh rendering of all standard audiences.
- Peak worker CPU and memory usage.
- Custom-report resource-link and browser inspection.
- Full test-suite and current fork CI results.
- Source license and attribution requirements.
- Web input, authorization, sharing and retention contracts.
- Production security, concurrency and restart recovery.

Preserve the existing pipeline and its scientific checks.
Do not equate a working website with a verified scientific release.

## Request adapter implementation checkpoint

Recorded: 2026-10-11

- Existing Python suite: 131 passed in 11.48 seconds.
- Six audience/window rendering smoke tests completed successfully.
- Window experiment: results/web-windows-yR2oMx.
- Adapter tests: 28 passed in 2.22 seconds.
- Complete suite with adapter: 159 passed in 11.60 seconds.
- Adapter render experiment: results/web-adapter-MuZbsu.
- All three adapter-generated 2022–2025 reports rendered successfully.
- Printed provenance confirmed requested years, CHFL geography,
  2019 reference/base years, preserved scientific policy,
  and audience-specific presentation.
- Core report artifacts were present and non-empty.

Limitations:
- Adapter HTML wording and resource links still require inspection.
- No API, queue, worker service or deployment has been implemented.
- Current Dockerfile.report installs UI dependencies including Marimo.
- Production Marimo removal and regression checks remain required.
- Licensing and earlier outstanding release checks remain unresolved.

Earlier outstanding-check lists describe the baseline at that time;
this section records subsequent progress.
