"""Report-container configuration must remain aligned and exercised in CI."""
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_report_image_matches_toolchain_contract():
    contract = json.loads((ROOT / "workflow/toolchain.json").read_text())
    dockerfile = (ROOT / "Dockerfile.report").read_text()

    assert f'FROM rocker/r-ver:{contract["r"]["validated"]}' in dockerfile
    assert f'uv python install {contract["python"]["validated"]}' in dockerfile
    assert f'ARG QUARTO_VERSION={contract["quarto"]["validated"]}' in dockerfile
    assert f'ARG UV_VERSION={contract["uv"]["validated"]}' in dockerfile
    assert f'install_tinytex.sh {contract["tinytex"]["validated"]}' in dockerfile
    assert "requirements.lock.txt" in dockerfile
    assert "Rscript workflow/restore_r.R" in dockerfile
    assert "libuv1-dev" in dockerfile


def test_report_service_does_not_require_github_credentials():
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text())
    report = compose["services"]["report"]

    assert report["build"]["dockerfile"] == "Dockerfile.report"
    assert report["command"] == ["snakemake", "--cores", "2"]

    environment = report.get("environment", {})
    assert not any(name.startswith("GITHUB_") for name in environment)
    assert "LINEAGE_RUN_ID" not in environment
    assert environment["HEALTH_REPORT_R_LIBRARY"] == "/opt/health-report-r-library"


def test_ci_builds_and_verifies_reports_inside_container():
    workflow = yaml.safe_load(
        (ROOT / ".github/workflows/validate.yml").read_text()
    )
    steps = workflow["jobs"]["container"]["steps"]

    build = next(
        i for i, step in enumerate(steps)
        if "--file Dockerfile.report" in step.get("run", "")
    )
    render = next(
        i for i, step in enumerate(steps)
        if "health-report:reports-ci" in step.get("run", "")
        and "snakemake --cores 2" in step.get("run", "")
    )
    verify = next(
        i for i, step in enumerate(steps)
        if "check_outputs.py" in step.get("run", "")
    )

    assert build < render < verify
    verification = steps[verify]["run"]

    for required in (
        "verify_release.py",
        "shiny_smoke.R",
        "dashboard_smoke.R",
        "Nothing to be done",
    ):
        assert required in verification

    assert all("continue-on-error" not in step for step in steps)
