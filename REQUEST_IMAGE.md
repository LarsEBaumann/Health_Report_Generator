# Request environment image: test branch only

Purpose: install report software when building an image, then reuse that image for requests. This stage builds and tests the image; the working `request-report.yml` job is deliberately not switched until an image passes.

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

## Next gate

After a green build/test/publish run, supply the exact digest from `image-reference.txt`. A separate change will make the request workflow use it and remove per-request installation steps. Do not use `latest` or assume a tag can never change. Record the chosen image digest with report provenance when enabling that route.

This workflow neither changes other branches nor merges anything. It creates a separately named GHCR package in the workflow repository owner's namespace when publication is allowed. It does not change package visibility or existing image tags.

## Limits

The local authoring environment did not have Docker available; an actual container build is still required in Actions. Do not claim a faster request before timing a request against the published image. Image pull, runner startup and queue time remain. Prepared-data reuse across different GitHub runs is a separate change.

This is an amd64 image intended for the GitHub Linux runner. Running it on Apple Silicon would require an explicit emulation test; it is not a native Mac/ARM support claim. No local Docker installation is needed for the GitHub build.
