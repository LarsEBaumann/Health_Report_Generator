import json
#import os
import uuid
from pathlib import Path

import marimo

__generated_with = "0.25.1"
app = marimo.App(width="medium")

@app.cell
def _():
    import os
    from pathlib import Path

    import marimo as mo
    import requests

    return Path, mo, os, requests

from artifact_download import download_latest_report

reports_dir, run, artifact = download_latest_report()

'''def lineage_root() -> Path:
    root = Path(os.getenv("LINEAGE_DIR", "data/lineage"))
    matches = sorted(root.rglob("harmonised.parquet"), key=lambda p: len(p.parts))
    if not matches:
        raise FileNotFoundError(
            "No downloaded lineage artifact. Set LINEAGE_DIR to an extracted health-report artifact."
        )
    return matches[0].parent'''
'''
def catalog(root: Path):
    import pandas as pd

    bundle = root / "reports/public_health_expert/data"
    series = pd.read_csv(bundle / "series.csv").fillna("")
    selection = pd.read_csv(bundle / "selection.csv").fillna("")
    allowed = set(
        selection.loc[
            selection.status.astype(str).str.lower().eq("included")
            & selection.group_eligible.astype(str).str.lower().isin(["true", "1"]),
            "dataset_id",
        ].astype(str)
    )
    return series[
        series.dataset_id.astype(str).isin(allowed)
        & series.pathogen_class.isin(["viral", "bacterial"])
    ].drop_duplicates("dataset_id").sort_values(["pathogen_class", "label"])
'''
'''
@app.cell
def _(Path, mo, os):
    import pandas as pd

    def lineage_root():
        root = Path(os.getenv("LINEAGE_DIR", "data/lineage"))
        matches = sorted(
            root.rglob("harmonised.parquet"),
            key=lambda path: len(path.parts),
        )
        if not matches:
            raise FileNotFoundError(
                "No downloaded lineage artifact. "
                "Set LINEAGE_DIR to an extracted health-report artifact."
            )
        return matches[0].parent

    def catalog(root):
        bundle = root / "reports/public_health_expert/data"
        series = pd.read_csv(bundle / "series.csv").fillna("")
        selection = pd.read_csv(bundle / "selection.csv").fillna("")

        allowed = set(
            selection.loc[
                selection.status.astype(str).str.lower().eq("included")
                & selection.group_eligible.astype(str)
                .str.lower()
                .isin(["true", "1"]),
                "dataset_id",
            ].astype(str)
        )
'''
        return series[
            series.dataset_id.astype(str).isin(allowed)
            & series.pathogen_class.isin(["viral", "bacterial"])
        ].drop_duplicates("dataset_id").sort_values(
            ["pathogen_class", "label"]
        )

    try:
        root = lineage_root()
        datasets = catalog(root)
        ready = True
        message = None
    except Exception as exc:
        root, datasets, ready, message = None, None, False, str(exc)

    return datasets, message, ready, root

@app.cell
def _(datasets, mo, ready):
    audience_widget = mo.ui.dropdown(
        options={
            "Researcher": "researcher",
            "Policy maker": "policy_maker",
            "General public": "general_public",
        },
        value="Researcher",
        label="Who is this report for?",
        full_width=True,
    )
    options = (
        {f"{row.label} ({row.pathogen_class})": row.dataset_id for row in datasets.itertuples()}
        if ready
        else {}
    )
    selected = mo.ui.multiselect(
        options=options,
        label="Diseases to include",
        full_width=True,
    )
    report_form = mo.ui.form(
        mo.md("## Create a report\n\n{audience}\n\n{selected}").batch(
            audience=audience_widget, selected=selected
        ),
        submit_button_label="Generate report",
        submit_button_disabled=not ready,
    )
    return audience_widget, report_form, selected


@app.cell
def _(message, mo, ready, report_form, requests):
    if not ready:
        result = mo.callout(mo.md(f"**Lineage artifact required:** `{message}`"), kind="warn")
    elif report_form.value is None:
        result = mo.md("Choose a stakeholder and one or more diseases, then select **Generate report**.")
    else:
        audience_name = report_form.value["audience"]
        dataset_ids = report_form.value["selected"]
        if not dataset_ids:
            result = mo.callout(mo.md("Select at least one disease."), kind="warn")
        else:
            token = os.getenv("GITHUB_TOKEN")
            run_id = os.getenv("LINEAGE_RUN_ID")
            repository = os.getenv("GITHUB_REPOSITORY", "LarsEBaumann/Health_Report_Generator")
            request_id = uuid.uuid4().hex
            if not token or not run_id:
                result = mo.callout(
                    mo.md("Set `GITHUB_TOKEN` and `LINEAGE_RUN_ID` before generating a report."),
                    kind="warn",
                )
            else:
                response = requests.post(
                    f"https://api.github.com/repos/{repository}/actions/workflows/render-selected-report.yml/dispatches",
                    headers={"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}"},
                    json={
                        "ref": "connector",
                        "inputs": {
                            "request_id": request_id,
                            "lineage_run_id": str(run_id),
                            "audience": audience_name,
                            "dataset_ids_json": json.dumps(dataset_ids),
                        },
                    },
                    timeout=30,
                )
                if response.status_code == 204:
                    result = mo.callout(
                        mo.md(
                            f"Report requested (`{request_id}`). Open [GitHub Actions](https://github.com/{repository}/actions/workflows/render-selected-report.yml) to retrieve the generated HTML artifact when the run completes."
                        ),
                        kind="success",
                    )
                else:
                    result = mo.callout(
                        mo.md(f"GitHub Actions request failed ({response.status_code}): `{response.text}`"),
                        kind="danger",
                    )
    result


if __name__ == "__main__":
    app.run()
