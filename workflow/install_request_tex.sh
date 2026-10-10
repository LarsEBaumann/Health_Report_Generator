#!/usr/bin/env bash
# Container build only; never replaces a host user's TeX installation.
set -euo pipefail
if [[ "$(uname -s)" != Linux || "$(uname -m)" != x86_64 ]]; then
  echo 'This installer requires a Linux x86_64 container.' >&2
  exit 2
fi
if [[ -e /opt/tex/.TinyTeX ]]; then
  echo 'Refusing to overwrite /opt/tex/.TinyTeX.' >&2
  exit 2
fi
archive=$(mktemp /tmp/request-tex.XXXXXXXX)
trap 'rm -f "$archive"' EXIT
curl --fail --show-error --location --retry 5 --retry-all-errors \
  --output "$archive" \
  https://github.com/rstudio/tinytex-releases/releases/download/v2026.10/TinyTeX-linux-x86_64-v2026.10.tar.xz
echo "54fec1c79ab437d2d52e2f918bdb738c85779d654a93e62cc44f022e227692b5  $archive" | sha256sum --check --status
mkdir -p /opt/tex
tar -xJf "$archive" -C /opt/tex
chmod -R a+rX /opt/tex/.TinyTeX
/opt/tex/.TinyTeX/bin/x86_64-linux/tlmgr --version
/opt/tex/.TinyTeX/bin/x86_64-linux/kpsewhich scrartcl.cls >/dev/null
