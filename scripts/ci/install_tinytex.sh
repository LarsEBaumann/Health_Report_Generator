#!/usr/bin/env bash
set -euo pipefail

version="2026.10"
asset="TinyTeX-linux-x86_64-v2026.10.tar.xz"
expected_sha256="54fec1c79ab437d2d52e2f918bdb738c85779d654a93e62cc44f022e227692b5"
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

tinytex_bin="$HOME/.TinyTeX/bin/x86_64-linux"
echo "$tinytex_bin" >> "$GITHUB_PATH"
"$tinytex_bin/tlmgr" --version
"$tinytex_bin/kpsewhich" scrartcl.cls >/dev/null || {
  echo "Pinned TinyTeX bundle does not contain required class scrartcl.cls" >&2
  exit 3
}
