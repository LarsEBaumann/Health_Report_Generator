import json
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / "workflow/toolchain.json").read_text())
WORKFLOWS = (
    ".github/workflows/validate.yml",
    ".github/workflows/update-lyme-data.yml",
    ".github/workflows/render-selected-report.yml",
)


def text(path: str) -> str:
    return (ROOT / path).read_text()


def test_python_contract_is_aligned():
    supported = CONTRACT["python"]["supported"]
    validated = CONTRACT["python"]["validated"]
    project = tomllib.loads(text("pyproject.toml"))
    assert project["project"]["requires-python"] == supported
    assert f"python={validated}" in text("workflow/environment.yml")
    assert f"FROM python:{validated}-slim" in text("Dockerfile")
    for workflow in WORKFLOWS:
        assert f'python-version: "{validated}"' in text(workflow).replace("'", '"')


def test_r_and_quarto_contract_is_aligned():
    r_version = CONTRACT["r"]["validated"]
    quarto_version = CONTRACT["quarto"]["validated"]
    assert f"r-base={r_version}" in text("workflow/environment.yml")
    assert f"ARG QUARTO_VERSION={quarto_version}" in text("Dockerfile")
    for workflow in WORKFLOWS:
        content = text(workflow).replace("'", '"')
        assert f'r-version: "{r_version}"' in content
        assert f'version: "{quarto_version}"' in content


def test_tinytex_contract_is_aligned():
    tinytex = CONTRACT["tinytex"]
    installer = text("scripts/ci/install_tinytex.sh")
    assert f'version="{tinytex["validated"]}"' in installer
    assert f'asset="{tinytex["asset"]}"' in installer
    assert f'expected_sha256="{tinytex["sha256"]}"' in installer
    assert 'requested_version="${1:-$version}"' in installer
    assert tinytex["bundle"] == "TinyTeX"
    for required_file in tinytex["required_latex_files"]:
        assert f'kpsewhich" {required_file}' in installer
    for workflow in WORKFLOWS:
        content = text(workflow)
        assert "tinytex: true" not in content
        assert f'install_tinytex.sh {tinytex["validated"]}' in content


def test_validation_runs_for_push_and_pull_requests():
    workflow = text(".github/workflows/validate.yml")
    assert "  push:" in workflow
    assert "  pull_request:" in workflow


def test_workflow_branch_refs_are_main():
    for workflow in (
        ".github/workflows/update-lyme-data.yml",
        ".github/workflows/render-selected-report.yml",
    ):
        content = text(workflow)
        assert "ref: main" in content
        assert "ref: connector" not in content
    assert 'os.getenv("GITHUB_APP_REF", "main")' in text("src/ui.py")
    assert 'os.getenv("GITHUB_APP_REF", "connector")' not in text("src/ui.py")
    assert "`connector` branch" not in text("CONNECTOR_SETUP.md")


def test_documentation_names_authoritative_contract():
    for path in ("README.md", "GETTING_STARTED.md"):
        assert "workflow/toolchain.json" in text(path)


def test_uv_version_is_aligned():
    assert f'ARG UV_VERSION={CONTRACT["uv"]["validated"]}' in text("Dockerfile")


def test_canonical_data_root_is_used_everywhere_active():
    config = text("workflow/config.yaml")
    assert "data_root: data/reference" in config
    for workflow in WORKFLOWS:
        content = text(workflow)
        assert "data_root=Data" not in content
    migration = json.loads(text("docs/phase-3-data-migration.json"))
    assert migration["canonical_root"] == "data/reference"
    assert migration["legacy_root"] == "Data"
    assert migration["unmapped_legacy_directories"] == 0
    assert len(migration["entries"]) == migration["legacy_dataset_directories"] == 37
