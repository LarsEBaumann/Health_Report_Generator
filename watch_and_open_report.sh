#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'HELP'
Usage: bash watch_and_open_report.sh REQUEST_ID [OWNER/REPO] [DESTINATION]

Watch an existing selected-report request and download its artifact.
This script does not generate a new request.

Repository: argument 2, GITHUB_REPOSITORY, or GITHUB_OWNER/GITHUB_REPO.
Destination: argument 3, REPORT_DOWNLOAD_DIR, or outputs/selected-reports
relative to this script.

Set REPORT_OPEN=0 to skip opening the downloaded HTML.
GitHub CLI (gh) and authenticated repository access are required.
HELP
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

if (( $# < 1 || $# > 3 )); then
  usage >&2
  exit 2
fi

request_id="$1"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo="${2:-${GITHUB_REPOSITORY:-}}"

if [[ -z "$repo" && -n "${GITHUB_OWNER:-}" && -n "${GITHUB_REPO:-}" ]]; then
  repo="${GITHUB_OWNER}/${GITHUB_REPO}"
fi

dest="${3:-${REPORT_DOWNLOAD_DIR:-$script_dir/outputs/selected-reports}}"
workflow="render-selected-report.yml"

if [[ ! "$request_id" =~ ^[A-Za-z0-9_-]{8,40}$ ]]; then
  echo "Invalid request ID: use 8-40 letters, digits, underscores or hyphens." >&2
  exit 2
fi

if [[ ! "$repo" =~ ^[A-Za-z0-9-]+/[A-Za-z0-9_.-]+$ ]] ||
   [[ "${repo#*/}" == "." || "${repo#*/}" == ".." ]]; then
  echo "Set GITHUB_REPOSITORY=owner/repo or pass OWNER/REPO as argument 2." >&2
  exit 2
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "GitHub CLI (gh) is required. Install it and authenticate." >&2
  exit 2
fi

run_id=""
deadline=$((SECONDS + 300))

printf 'Repository: %s\nDestination: %s\n' "$repo" "$dest"
echo "Waiting for request $request_id..."

while [[ -z "$run_id" && $SECONDS -lt $deadline ]]; do
  run_id="$(
    gh run list --repo "$repo" --workflow "$workflow" --limit 100 \
      --json databaseId,displayTitle \
      --jq "[.[] | select(.displayTitle == \"Selected report $request_id\")][0].databaseId // empty"
  )"
  [[ -n "$run_id" ]] || sleep 5
done

if [[ -z "$run_id" ]]; then
  echo "No workflow run found for request $request_id in $repo within 300 seconds." >&2
  exit 1
fi

echo "Watching GitHub run $run_id..."
if ! gh run watch "$run_id" --repo "$repo" --exit-status; then
  echo "Run did not succeed. Inspect the failed steps with:" >&2
  printf 'gh run view %q --repo %q --log-failed\n' "$run_id" "$repo" >&2
  exit 1
fi

mkdir -p -- "$dest"
dest="$(cd -- "$dest" && pwd)"
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

if [[ "${REPORT_OPEN:-1}" == "0" ]]; then
  exit 0
fi

if command -v explorer.exe >/dev/null 2>&1 &&
   command -v wslpath >/dev/null 2>&1; then
  if explorer.exe "$(wslpath -w "$report")"; then
    exit 0
  fi
elif command -v xdg-open >/dev/null 2>&1; then
  if xdg-open "$report"; then
    exit 0
  fi
elif command -v open >/dev/null 2>&1; then
  if open "$report"; then
    exit 0
  fi
fi

printf 'Download succeeded. Open this file manually:\n%s\n' "$report"
exit 0
