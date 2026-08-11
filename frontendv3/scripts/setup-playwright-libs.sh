#!/usr/bin/env bash
#
# Setup Playwright's missing system libraries WITHOUT root.
#
# Vitest runs Playwright/Chromium in browser mode, but some CI/dev images are
# missing the Chromium runtime libraries (libnspr4, libnss3, libasound2).
# There is no devcontainer in this project and /tmp does not persist between
# sessions, so this script downloads + extracts the .debs into the project so
# tests can run via LD_LIBRARY_PATH (no sudo required).
#
# Usage (run once after a fresh environment):
#   bash scripts/setup-playwright-libs.sh
#
# Then run tests with the library path:
#   LD_LIBRARY_PATH="$(pwd)/.playwright-libs/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH" pnpm test

set -euo pipefail

# Target directory is <repo>/frontendv3/.playwright-libs
DEST="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/.playwright-libs"
LIBDIR="$DEST/usr/lib/x86_64-linux-gnu"
mkdir -p "$LIBDIR"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# archive.ubuntu.com pool paths (amd64). SONAME-stable: libnspr4.so / libnss3.so / libasound.so.2
BASE="http://archive.ubuntu.com/ubuntu/pool/main"
URLS=(
  "n/nspr/libnspr4_4.39-1ubuntu1_amd64.deb"
  "n/nss/libnss3_3.126-1_amd64.deb"
  "a/alsa-lib/libasound2_1.2.6.1-1ubuntu1.2_amd64.deb"
)

echo "Fetching Playwright runtime libraries into ${DEST} ..."
for rel in "${URLS[@]}"; do
  url="${BASE}/${rel}"
  name="$(basename "${rel}")"
  echo "  downloading ${name}"
  curl -fsSL -o "${WORK}/${name}" "${url}" \
    || { echo "  FAILED: ${url}" >&2; exit 1; }
  dpkg -x "${WORK}/${name}" "${DEST}"
  echo "  extracted ${name}"
done

# Sanity check
missing=0
for so in libnspr4.so libnss3.so libnssutil3.so libasound.so.2; do
  if [ ! -e "${LIBDIR}/${so}" ]; then
    echo "  ERROR: ${so} not found after extraction" >&2
    missing=1
  fi
done
if [ "${missing}" -ne 0 ]; then
  exit 1
fi

echo
echo "Done. Run tests with:"
echo "  LD_LIBRARY_PATH=\"${LIBDIR}:\$LD_LIBRARY_PATH\" pnpm test"
