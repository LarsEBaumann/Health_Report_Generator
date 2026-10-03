#!/usr/bin/env bash
# One command for the whole workflow:  bash run_all.sh data/Data out
set -euo pipefail
DATA=${1:-data/Data}; OUT=${2:-out}
HERE="$(cd "$(dirname "$0")" && pwd)"
python "$HERE/harmonise.py" "$DATA" --out "$OUT"
python "$HERE/checks.py" --out "$OUT"
for s in "$HERE"/config/stakeholders/*.json; do
  python "$HERE/report.py" --stakeholder "$s" --out "$OUT"
done
echo "Done. Open $OUT/report_*.html"
