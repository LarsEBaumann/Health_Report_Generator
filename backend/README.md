# Health report pipeline

See the [repository README](../../README.md) for setup, Snakemake targets, reproducibility, quality policy and outputs.

The processing stages are `inventory.py`, `harmonise.py`, `checks.py`, `analyse.py`, `publish.py`, and `release.py`. `report.py` is a compatibility entry point using the same analysis and QMD. It requires a successfully validated output directory. `mock_test.py` now runs the correctness regression suite; it no longer labels merely surviving damaged input as a pass.

`report_public_health_expert.qmd` is a generic presentation template despite its historical filename. The workflow copies it as `report.qmd` beside the validated CSVs and shared R helpers in each app bundle. Render that packaged copy, not this source file without its data.

Schema and lineage: [SCHEMA.md](SCHEMA.md).
