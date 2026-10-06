import marimo

__generated_with = "0.25.1"
app = marimo.App(width="medium")


@app.cell
def _():
    import json
    import os
    import uuid

    import marimo as mo
    import pandas as pd
    import requests

    from artifact_download import download_latest_report

    return download_latest_report, json, mo, os, pd, requests, uuid


@app.cell
def _(download_latest_report, pd):
    try:
        bundle_dir, source_run, source_artifact = download_latest_report()
        series = pd.read_csv(bundle_dir / "series.csv").fillna("")
        selection = pd.read_csv(bundle_dir / "selection.csv").fillna("")
        required_series = {"dataset_id", "pathogen_class", "label"}
        required_selection = {"dataset_id", "status", "group_eligible"}
        if not required_series.issubset(series.columns):
            raise ValueError(f"series.csv missing columns: {sorted(required_series - set(series.columns))}")
        if not required_selection.issubset(selection.columns):
            raise ValueError(f"selection.csv missing columns: {sorted(required_selection - set(selection.columns))}")
        eligible = selection[
            selection["status"].astype(str).str.lower().eq("included")
            & selection["group_eligible"].astype(str).str.lower().isin(["true", "1"])
        ]
        allowed = set(eligible["dataset_id"].astype(str))
        datasets = series[
            series["dataset_id"].astype(str).isin(allowed)
            & series["pathogen_class"].isin(["viral", "bacterial"])
        ].drop_duplicates("dataset_id").sort_values(["pathogen_class", "label"])
        ready = not datasets.empty
        message = None if ready else "No eligible viral or bacterial datasets were found."
    except Exception as exc:
        source_run = None
        source_artifact = None
        datasets = pd.DataFrame(columns=["dataset_id", "pathogen_class", "label"])
        ready = False
        message = str(exc)
    return datasets, message, ready, source_artifact, source_run


@app.cell
def _(datasets, message, mo, ready, source_artifact, source_run):
    audience_widget = mo.ui.dropdown(
        options={"Researcher": "researcher", "Public health": "policy_maker", "General public": "general_public"},
        value="Researcher",
        label="Who is this report for?",
        full_width=True,
    )
    def disease_options(pathogen_class):
        return {
            f"{row.label} [{row.dataset_id}]": str(row.dataset_id)
            for row in datasets[
                datasets["pathogen_class"].eq(pathogen_class)
            ].itertuples(index=False)
        } if ready else {}

    bacterial_widget = mo.ui.multiselect(
        options=disease_options("bacterial"),
        label="Bacterial diseases",
        full_width=True,
    )
    viral_widget = mo.ui.multiselect(
        options=disease_options("viral"),
        label="Viral diseases",
        full_width=True,
    )
    report_form = mo.ui.form(
        mo.md(
            "## Create a report\n\n{audience}\n\n"
            "Select bacterial diseases, viral diseases, or both. "
            "The report uses only your selected datasets.\n\n"
            "{bacterial}\n\n{viral}"
        ).batch(
            audience=audience_widget,
            bacterial=bacterial_widget,
            viral=viral_widget,
        ),
        submit_button_label="Generate report",
        submit_button_disabled=not ready or source_run is None,
    )
    if ready:
        status = mo.md(
            f"Data ready: {len(datasets)} eligible datasets from source run "
            f"`{source_run['run_number']}` (artifact `{source_artifact['name']}`)."
        )
    else:
        status = mo.callout(
            mo.md(f"Could not load report data: `{message}`"), kind="warn"
        )
    mo.vstack([status, report_form])
    return audience_widget, bacterial_widget, viral_widget, report_form


@app.cell
def _(json, mo, os, report_form, requests, source_run, uuid):
    if report_form.value is None:
        result = mo.md("Choose a stakeholder and diseases, then select **Generate report**.")
    else:
        values = report_form.value
        audience = values["audience"]
        dataset_ids = sorted(set(
            values["bacterial"] + values["viral"]
        ))
        if not dataset_ids:
            result = mo.callout(mo.md("Select at least one disease."), kind="warn")
        else:
            token = os.getenv("GITHUB_TOKEN")
            owner = os.getenv("GITHUB_OWNER", "LarsEBaumann")
            repo = os.getenv("GITHUB_REPO", "Health_Report_Generator")
            ref = os.getenv("GITHUB_APP_REF", "main")
            if not token:
                result = mo.callout(mo.md("Set GITHUB_TOKEN with Actions read/write permission."), kind="warn")
            else:
                request_id = uuid.uuid4().hex
                url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/render-selected-report.yml/dispatches"
                headers = {
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {token}",
                    "X-GitHub-Api-Version": "2022-11-28",
                }
                try:
                    response = requests.post(
                        url, headers=headers,
                        json={"ref": ref, "inputs": {
                            "request_id": request_id,
                            "lineage_run_id": str(source_run["id"]),
                            "audience": audience,
                            "dataset_ids_json": json.dumps(dataset_ids),
                        }},
                        timeout=30,
                    )
                    if response.status_code == 204:
                        result = mo.callout(
                            mo.md(
                                f"Report request `{request_id}` queued using source run "
                                f"`{source_run['run_number']}`. Check [GitHub Actions]"
                                f"(https://github.com/{owner}/{repo}/actions/workflows/render-selected-report.yml) "
                                "for completion and the selected-report artifact."
                            ), kind="success"
                        )
                    else:
                        result = mo.callout(
                            mo.md(f"Workflow dispatch failed ({response.status_code}): `{response.text}`"),
                            kind="danger",
                        )
                except requests.RequestException as exc:
                    result = mo.callout(mo.md(f"Could not contact GitHub: `{exc}`"), kind="danger")
    result


if __name__ == "__main__":
    app.run()
