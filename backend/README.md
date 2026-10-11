# Health report pipeline

See the [repository README](../../README.md) for setup, Snakemake targets, reproducibility, quality policy and outputs.

The processing stages are `inventory.py`, `harmonise.py`, `checks.py`, `analyse.py`, `publish.py`, and `release.py`. The Quarto reports are rendered by `render_quarto.py` from the table `export_csv.py` writes. Run the regression suite with `python run.py test`.

`report_public_health_expert.qmd` is a generic presentation template despite its historical filename. The workflow copies it as `report.qmd` beside the validated CSVs and shared R helpers in each app bundle. Render that packaged copy, not this source file without its data.

Schema and lineage: [SCHEMA.md](SCHEMA.md).
