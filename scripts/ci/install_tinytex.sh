#!/usr/bin/env bash
set -euo pipefail

version="${1:-2026.10}"
asset="TinyTeX-1-linux-x86_64-v${version}.tar.xz"
url="https://github.com/rstudio/tinytex-releases/releases/download/v${version}/${asset}"
expected_sha256="4d519d6236ee6798e3ec0d8e2093d1fda01aeb267aa22c2a5586d76bcfce6566"
archive="$(mktemp)"
trap 'rm -f "$archive"' EXIT

curl --fail --location --retry 5 --retry-all-errors --output "$archive" "$url"
echo "${expected_sha256}  ${archive}" | sha256sum --check --status
rm -rf "$HOME/.TinyTeX"
tar -xJf "$archive" -C "$HOME"

echo "$HOME/.TinyTeX/bin/x86_64-linux" >> "$GITHUB_PATH"
"$HOME/.TinyTeX/bin/x86_64-linux/tlmgr" --version
