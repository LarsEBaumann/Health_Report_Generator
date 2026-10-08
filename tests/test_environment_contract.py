import json
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / "workflow/toolchain.json").read_text())


def text(path: str) -> str:
    return (ROOT / path).read_text()


def test_python_contract_is_aligned():
    supported = CONTRACT["python"]["supported"]
    validated = CONTRACT["python"]["validated"]
    project = tomllib.loads(text("pyproject.toml"))
    assert project["project"]["requires-python"] == supported
    assert f"python={validated}" in text("workflow/environment.yml")
    assert f"FROM python:{validated}-slim" in text("Dockerfile")
    for workflow in (
        ".github/workflows/validate.yml",
        ".github/workflows/update-lyme-data.yml",
        ".github/workflows/render-selected-report.yml",
    ):
        assert f'python-version: "{validated}"' in text(workflow).replace("'", '"')


def test_r_and_quarto_contract_is_aligned():
    r_version = CONTRACT["r"]["validated"]
    quarto_version = CONTRACT["quarto"]["validated"]
    assert f"r-base={r_version}" in text("workflow/environment.yml")
    assert f"ARG QUARTO_VERSION={quarto_version}" in text("Dockerfile")
    for workflow in (
        ".github/workflows/validate.yml",
        ".github/workflows/update-lyme-data.yml",
        ".github/workflows/render-selected-report.yml",
    ):
        content = text(workflow).replace("'", '"')
        assert f'r-version: "{r_version}"' in content
        assert f'version: "{quarto_version}"' in content


def test_documentation_names_authoritative_contract():
    for path in ("README.md", "GETTING_STARTED.md"):
        assert "workflow/toolchain.json" in text(path)


def test_uv_version_is_aligned():
    assert f'ARG UV_VERSION={CONTRACT["uv"]["validated"]}' in text("Dockerfile")
