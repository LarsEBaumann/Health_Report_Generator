# Release checklist

Run from a clean checkout of `main` after all phase pull requests are merged. Tagging is a maintainer action; nothing here is automated.

1. **CI green on `main`** for push and pull request: `fast`, `secrets`, `container`, `full` (when the Phase 6 jobs are present).
2. **Fresh-clone check** on a clean machine or container:
   ```sh
   git clone https://github.com/LarsEBaumann/Health_Report_Generator.git && cd Health_Report_Generator
   # install steps from docs/reproduction.md, then:
   snakemake --cores 2
   python scripts/health_pipeline/check_outputs.py
   python -m pytest -q
   ```
   Expect three audience folders under `results/reports/`, each with `report.html`, `methods.html`, PDFs and `provenance.json`.
3. **Data version.** Confirm the snapshot id and dates in `results/reports/public/provenance.json`; update the date and id in the release notes if you quote them.
4. **Limitations and citation.** Review `docs/limitations.md` and `CITATION.cff` (authors, version, date).
5. **Licence decision.** Add a `LICENSE` file chosen by the repository owner, and update `data/README.md`. Source data terms (source attribution) stay with the data.
6. **Tag and publish.**
   ```sh
   git tag -a v1.0.0 -m "Hackathon release"
   git push origin v1.0.0
   ```
   Attach the CI artifact `health-report-<sha>` (or the three `report.html` folders) to the GitHub release, and paste the notes from `RELEASE_NOTES.md`.
7. **Archive.** Keep `results/snapshots/<snapshot_id>/` with the release so it can be reproduced offline.
