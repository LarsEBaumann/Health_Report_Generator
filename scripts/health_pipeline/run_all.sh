#!/usr/bin/env bash
# One command for the whole workflow: builds every audience report listed in
# workflow/config.yaml (HTML, PDF, Shiny package, provenance, release.json).
#
#   bash scripts/health_pipeline/run_all.sh [data_root] [out_dir] [extra snakemake args...]
#
# Defaults come from workflow/config.yaml (data/reference, results). Set QUARTO to
# override the renderer path and CORES to change parallelism (default 2).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
overrides=()
[[ -n "${1:-}" ]] && overrides+=("data_root=$1")
[[ -n "${2:-}" ]] && overrides+=("out=$2")
[[ -n "${QUARTO:-}" ]] && overrides+=("quarto=$QUARTO")
shift $(( $# > 2 ? 2 : $# ))
exec snakemake --cores "${CORES:-2}" ${overrides[@]+--config "${overrides[@]}"} "$@"
