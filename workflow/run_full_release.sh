#!/usr/bin/env bash
# Full reproducible release: legacy Shiny bundle plus all three selected-data reports.
set -euo pipefail
cores="${1:-2}"

snakemake --cores "$cores"
python scripts/health_pipeline/full_release.py \
  --selection results/reports/public_health_expert/data/selection.csv \
  --out results/full-release-requests
for request in results/full-release-requests/researcher.json \
               results/full-release-requests/health_institution.json \
               results/full-release-requests/public.json; do
  snakemake --cores "$cores" --config request_file="$request"
done
