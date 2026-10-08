#!/usr/bin/env bash
# Scan the repository history for committed secrets with a pinned, checksum-verified gitleaks.
set -euo pipefail
version="8.30.1"
asset="gitleaks_${version}_linux_x64.tar.gz"
expected_sha256="551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
curl --fail --location --retry 5 --retry-all-errors --output "$work/$asset" \
  "https://github.com/gitleaks/gitleaks/releases/download/v${version}/${asset}"
echo "${expected_sha256}  $work/$asset" | sha256sum --check --status
tar -xzf "$work/$asset" -C "$work" gitleaks
"$work/gitleaks" git --no-banner --redact --exit-code 1 "${1:-.}"
