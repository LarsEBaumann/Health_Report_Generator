# Request environment image: test branch only

Purpose: install report software when building an image, then reuse that image for requests. The image passed build and offline report tests in run 38077323216. Normal request runs 38078992233 and 38079569356 also succeeded; the latter records the actual checkout commit in both embedded and sidecar provenance.

## What changes

- `Dockerfile.request`: Linux x86_64 environment with Python 3.11.6, Snakemake and the pinned Python packages, R 4.3.2 and restored R packages, Quarto 1.3.353, and checksum-verified TinyTeX 2026.10. It contains environment build inputs, not source data, reports, credentials or the repository checkout.
- `Dockerfile.request.dockerignore`: only required environment inputs enter the build context.
- `.Rprofile`: use `HEALTH_REPORT_R_LIBRARY` when explicitly configured by the image; retain the existing local `.r-library` behaviour otherwise.
- `workflow/install_request_tex.sh`: container-only installation under `/opt/tex`; refuses an existing installation and does not change a host user's TeX installation.
- `workflow/test_request_image.py`: regression tests, HTML-only request, researcher HTML/PDF request, artifact hashes and provenance, identical analysis across audiences, preparation reuse and no-work rerun.
- `.github/workflows/request-image.yml`: build, test without container network access, then publish the exact tested image. Push triggers are restricted to `test` and the environment-related files. Manual runs on other branches are skipped.

## First remote test

Commit only these seven files on `test` and push. Existing workflows can run too. Open **Build and test request environment** for this test, not either report workflow.

The first build installs all dependencies and can take significantly longer than a report run. Later environment builds can reuse Docker layers. Changing a dataset/audience does not rebuild the environment image. Code-only changes do not trigger this image build; test those against the published image in code CI once that connection is added.

Before publishing, the job runs the example through the image with `--network none`. This checks that report execution needs no package downloads. It mounts the checked-out code and committed source data at runtime and runs as the runner user, not container root.

The test image name is derived from the repository:

```
ghcr.io/<lowercase-owner>/<lowercase-repository>-request-test:sha-<commit>
```

The job requests `packages: write` for its automatic `GITHUB_TOKEN`. No personal token is required by this workflow. Repository/organisation policy can still deny publication. If publication fails, do not alter access settings automatically; inspect the error. The successful test artifact is uploaded before publication so its evidence remains available.

Artifacts:

- `request-image-test-<run-id>`: generated test reports and `image-test.json` with timings; also the built image inspection record.
- `request-image-reference-<run-id>`: `image-reference.txt`, the published `ghcr.io/...@sha256:...` reference.

## Active request environment

`request-report.yml` is pinned to:

```
ghcr.io/larsebaumann/health_report_generator-request-test@sha256:86f29ed4333f29648d13bfa007b157d232abc196d720edb41d4d2c83a79e721a
```

The job authenticates using the repository's automatic token with `packages: read`. There are no Python/R/Quarto/TeX installation steps. It compares repository dependency locks with those in the image, failing explicitly if they differ. Regression tests run on code pushes; every report still performs request validation, data checks and bundle integrity verification. Report provenance records the image reference under `software.container_image` (null for native runs without an image).

Push this change on `test`, then inspect **Build requested health report**. It should initialise the container, verify the environment, and generate the requested report. Download `requested-health-report-<run-id>` and check its request and provenance. This push does not rebuild the image unless an environment build input also changes. Compare complete run timings, including image pull and startup, before claiming a speed improvement.

When dependencies change, build/test a new image first and update both the container image and its provenance environment value to the new exact digest. Do not use `latest`. A fork needs access to this package or its own tested image; it must not silently fall back to an unverified environment.

This workflow neither changes other branches nor merges anything. It creates a separately named GHCR package in the workflow repository owner's namespace when publication is allowed. It does not change package visibility or existing image tags.

## Limits

The local authoring environment did not have Docker available. Container build and offline tests passed in Actions: first HTML generation took 28.620 seconds; a second audience with HTML/PDF took 17.441 seconds using the same preparation. These exclude initial build, queue and image-transfer time. Prepared-data reuse across different GitHub runs is described below; its remote timing must be measured separately.

This is an amd64 image intended for the GitHub Linux runner. Running it on Apple Silicon would require an explicit emulation test; it is not a native Mac/ARM support claim. No local Docker installation is needed for the GitHub build.

## Prepared-data cache between requests

The request job freezes and hashes the current source files, then restores an exact cache entry for the prepared data. The key includes the snapshot, preparation code, rule file, environment files, Python/pandas/pyarrow versions, and container image reference. It deliberately excludes audience, selected datasets, requested formats and the commit identifier. Code/environment changes covered by the key still invalidate it even when the data stays the same. Currently `request_pipeline.py` includes reporting code too, so edits there conservatively invalidate preparation.

Only the matching preparation directory is cached: not reports, requests, credentials, or Snakemake execution history. The workflow verifies every prepared file's checksum and its snapshot identity before use. Source snapshots are recreated and verified from the checkout on each run. Snakemake ignores timestamps for preparation inputs because content changes select a new preparation directory; this prevents a fresh checkout's timestamps from forcing unnecessary harmonisation. Selection, checks and rendering still run for each request.

On a miss, normal Snakemake preparation runs and the verified directory is saved after successful reporting. On a hit, it is reused. Corrupt entries fail explicitly instead of silently producing a report: delete the named cache in GitHub Actions' cache management and rerun. Cache eviction or an unavailable cache does not remove the ability to rebuild from the source. Concurrent misses may both prepare the same data; cache saving does not provide a job queue or lock.

### Acceptance test on `test`

1. Push the cache change. In **Build requested health report**, expect a first cache miss and a successful save. The run summary says **Prepared data built; cache save requested**; inspect the save step to confirm success.
2. Rerun that workflow at the same commit. The summary should say **Reused verified prepared data**, and the Snakemake job list must not contain `request_prepare`.
3. Submit another valid request on `test`, changing the audience and/or datasets while retaining the same code, data and image. Expect the same preparation cache key and a newly generated report matching that request.
4. Inspect `result.json`, the report, and `report.html.provenance.json`; the current request and actual commit must still be recorded.
5. Compare total run durations. A cache saves harmonisation work, but source hashing, runner startup, image pulling, rendering and artifact transfer remain. Do not assume every cache hit is faster for a small dataset.

No Docker image rebuild is needed for this cache change. GitHub cache restore/save follows the [official cache action documentation](https://github.com/actions/cache); no broad restore-prefix fallback is configured.
