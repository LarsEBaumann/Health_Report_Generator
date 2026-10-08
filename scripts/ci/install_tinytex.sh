#!/usr/bin/env bash
set -euo pipefail

version="2026.10"
asset="TinyTeX-1-linux-x86_64-v2026.10.tar.xz"
expected_sha256="4d519d6236ee6798e3ec0d8e2093d1fda01aeb267aa22c2a5586d76bcfce6566"
requested_version="${1:-$version}"

if [[ "$requested_version" != "$version" ]]; then
  echo "Unsupported TinyTeX version: $requested_version (locked version: $version)" >&2
  exit 2
fi

url="https://github.com/rstudio/tinytex-releases/releases/download/v${version}/${asset}"
archive="$(mktemp)"
trap 'rm -f "$archive"' EXIT

curl --fail --location --retry 5 --retry-all-errors --output "$archive" "$url"
echo "${expected_sha256}  ${archive}" | sha256sum --check --status
rm -rf "$HOME/.TinyTeX"
tar -xJf "$archive" -C "$HOME"

echo "$HOME/.TinyTeX/bin/x86_64-linux" >> "$GITHUB_PATH"
"$HOME/.TinyTeX/bin/x86_64-linux/tlmgr" --version
