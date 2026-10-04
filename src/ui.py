import marimo

__generated_with = "0.25.1"
app = marimo.App(width="medium")


@app.cell
def _():
    import json
    from pathlib import Path

    import marimo as mo
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator
    import pandas as pd
    import yaml

    return MaxNLocator, Path, json, mo, pd, plt, yaml


@app.cell
def _(Path, yaml):
    data_root = Path("data/reference")
    config_path = Path("configs/report.yml")

    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    default_dataset = config.get("dataset_id", "LYME_sentinella")

    dataset_ids = sorted(
        folder.name
        for folder in data_root.iterdir()
        if folder.is_dir() and (folder / "data.csv").is_file()
    ) if data_root.exists() else []

    def display_name(dataset_id):
        known = {
            "LYME_sentinella": "Lyme disease — Sentinella",
            "AIDS_oblig": "AIDS — mandatory reporting",
        }
        return known.get(dataset_id, dataset_id.replace("_", " — "))

    return dataset_ids, default_dataset, display_name


@app.cell
def _(dataset_ids, default_dataset, display_name, mo):
    audiences = ["Researcher", "Policy maker", "General public"]

    audience = mo.ui.dropdown(
        options=audiences,
        value="Researcher",
        label="Who is this report for?",
        full_width=True,
    )

    dataset_options = {
        display_name(dataset_id): dataset_id
        for dataset_id in dataset_ids
    }

    default_label = next(
        label
        for label, dataset_id in dataset_options.items()
        if dataset_id == default_dataset
    )

    datasets = mo.ui.multiselect(
        options=dataset_options,
        value=[default_label],
        label="Diseases / datasets to include",
        full_width=True,
    )

    report_form = mo.ui.form(
        mo.md(
            """
            ## Configure your report
            Choose an audience and the data to include.

            {audience}

            {datasets}
            """
        ).batch(audience=audience, datasets=datasets),
        submit_button_label="Generate report",
    )

    report_form
    return (report_form,)


@app.cell
def _(MaxNLocator, Path, display_name, json, mo, pd, plt, report_form):
    def render_dataset(dataset_id):
        csv_path = Path("data/reference") / dataset_id / "data.csv"
        metadata_path = Path("data/reference") / dataset_id / "metadata.json"

        if not csv_path.is_file():
            return [mo.md(f"Could not find `{csv_path}`.")]

        data = pd.read_csv(csv_path)
        output = []

        if metadata_path.is_file():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            retrieved = metadata.get("retrieved_at_utc", "unknown")
            output.append(mo.md(f"Source snapshot retrieved: `{retrieved}`."))

        if not {"temporal", "value"}.issubset(data.columns):
            output.append(
                mo.md("This dataset has no `temporal` and `value` pair for the prototype plot.")
            )
            output.append(mo.ui.table(data.head(15)))
            return output

        plot_data = data.copy()

        if "valueCategory" in plot_data.columns:
            categories = plot_data["valueCategory"].dropna().astype(str)
            if "cases" in categories.values:
                plot_data = plot_data[plot_data["valueCategory"].astype(str) == "cases"]

        if "temporal_type" in plot_data.columns:
            time_types = plot_data["temporal_type"].dropna().astype(str)
            if "month" in time_types.values:
                plot_data = plot_data[plot_data["temporal_type"].astype(str) == "month"]

        for column, preferred in [
            ("georegion", "CH"),
            ("agegroup", "all"),
            ("sex", "all"),
        ]:
            if column in plot_data.columns:
                values = plot_data[column].dropna().astype(str)
                if preferred in values.values:
                    plot_data = plot_data[plot_data[column].astype(str) == preferred]

        plot_data["value"] = pd.to_numeric(plot_data["value"], errors="coerce")
        plot_data = plot_data.dropna(subset=["temporal", "value"])
        plot_data["temporal"] = plot_data["temporal"].astype(str)

        if plot_data.empty or plot_data["temporal"].duplicated().any():
            output.append(
                mo.md(
                    "A single unambiguous time series could not be selected automatically. "
                    "Showing sample rows instead."
                )
            )
            output.append(mo.ui.table(data.head(15)))
            return output

        plot_data = plot_data.sort_values("temporal")
        fig, ax = plt.subplots(figsize=(9, 4))
        ax.plot(plot_data["temporal"], plot_data["value"], marker="o", linewidth=1.5)
        ax.set_title(display_name(dataset_id))
        ax.set_xlabel("Time")
        ax.set_ylabel("Value (source units)")
        ax.xaxis.set_major_locator(MaxNLocator(nbins=6))
        ax.tick_params(axis="x", rotation=60)
        fig.tight_layout()

        output.append(fig)
        return output

    if report_form.value is None:
        results = mo.md("Choose an audience and dataset, then click **Show results**.")
    else:
        audience_name = report_form.value["audience"]
        selected_ids = report_form.value["datasets"]

        if not selected_ids:
            results = mo.md("Select at least one dataset.")
        else:
            panels = [
                mo.md(
                    f"## {audience_name} view\n"
                    "The report content is currently shared across audiences; "
                    "audience-specific versions are a future step."
                )
            ]

            for dataset_id in selected_ids:
                panels.append(mo.md(f"### {display_name(dataset_id)}"))
                panels.extend(render_dataset(dataset_id))

            results = mo.vstack(panels)

    results
    return


if __name__ == "__main__":
    app.run()
