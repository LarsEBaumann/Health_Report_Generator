#!/usr/bin/env bash
set -euo pipefail

repo="LarsEBaumann/Health_Report_Generator"
workflow="render-selected-report.yml"
request_id="${1:?Usage: ./watch_and_open_report.sh REQUEST_ID}"
dest="/mnt/d/Studium/M.Sc. Medical Engineering/Hackathon"

if [[ ! "$request_id" =~ ^[A-Za-z0-9_-]{8,40}$ ]]; then
  echo "Invalid request ID." >&2
  exit 1
fi

run_id=""
deadline=$((SECONDS + 300))

echo "Waiting for request $request_id..."
while [[ -z "$run_id" && $SECONDS -lt $deadline ]]; do
  run_id="$(
    gh run list --repo "$repo" --workflow "$workflow" --limit 100 \
      --json databaseId,displayTitle \
      --jq ".[] | select(.displayTitle == \"Selected report $request_id\") | .databaseId" |
      head -n 1
  )"
  [[ -n "$run_id" ]] || sleep 5
done

if [[ -z "$run_id" ]]; then
  echo "No workflow run found for request $request_id." >&2
  exit 1
fi

echo "Watching GitHub run $run_id..."
if ! gh run watch "$run_id" --repo "$repo" --exit-status; then
  echo "Run did not succeed. Inspect the failed steps with:" >&2
  echo "gh run view $run_id --repo $repo --log-failed" >&2
  exit 1
fi

mkdir -p "$dest"
run_dir="$(mktemp -d "$dest/selected-report-${request_id}-XXXXXX")"

gh run download "$run_id" --repo "$repo" \
  --name "selected-report-$request_id" \
  --dir "$run_dir"

report="$run_dir/report.html"
if [[ ! -s "$report" ]]; then
  echo "Missing or empty report.html in $run_dir" >&2
  exit 1
fi

echo "Report saved in: $run_dir"
explorer.exe "$(wslpath -w "$report")"
