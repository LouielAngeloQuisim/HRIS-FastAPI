#!/usr/bin/env bash
#
# scripts/check-ci-config.sh - CI configuration check (roadmap #92).
#
# Validates every GitHub Actions workflow under .github/workflows/ with
# actionlint:
#   - YAML structure of each workflow file
#   - ${{ }} expression syntax and context access
#   - job references (needs), action inputs/outputs, reusable-workflow calls
#   - runner labels (ubuntu-26.04 is whitelisted in .github/actionlint.yaml)
#   - embedded shell in run: steps (via shellcheck when it is on PATH;
#     actionlint silently skips that layer otherwise)
# It does NOT validate .github/dependabot.yml (actionlint parses workflow
# files only) and does not run application tests.
#
# Reproducibility: actionlint is fetched pinned BY VERSION and pinned BY
# SHA256 from its official GitHub release assets, cached under
# .cache/actionlint/ (gitignored), and checksum-verified before every run.
# CI never pulls a floating binary. To bump: update ACTIONLINT_VERSION and
# both ACTIONLINT_SHA256_* values from the release's checksums file.
#
# Failure behavior: any actionlint problem is printed per-file/per-line and
# the script exits 1; exit 0 means every workflow validated clean.
#
# Usage:  bash scripts/check-ci-config.sh   (from anywhere; paths are absolute)

set -u
set -o pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

ACTIONLINT_VERSION="1.7.12"
ACTIONLINT_BASE="https://github.com/rhysd/actionlint/releases/download/v${ACTIONLINT_VERSION}"
# SHA256 of the official linux tarballs (verified 2026-09-29 by downloading
# both assets and comparing against the v1.7.12 release digests):
ACTIONLINT_SHA256_AMD64="8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8"
ACTIONLINT_SHA256_ARM64="325e971b6ba9bfa504672e29be93c24981eeb1c07576d730e9f7c8805afff0c6"

CACHE_DIR=".cache/actionlint"
BIN="${CACHE_DIR}/actionlint-${ACTIONLINT_VERSION}"
WORKFLOW_DIR=".github/workflows"
FAIL=0

download_actionlint() {
  local arch sha asset got
  arch="$(uname -m)"
  case "$arch" in
    x86_64) arch="amd64"; sha="$ACTIONLINT_SHA256_AMD64" ;;
    aarch64 | arm64) arch="arm64"; sha="$ACTIONLINT_SHA256_ARM64" ;;
    *) echo "unsupported architecture '$arch' for the pinned actionlint download"; return 1 ;;
  esac
  asset="actionlint_${ACTIONLINT_VERSION}_linux_${arch}.tar.gz"

  command -v curl >/dev/null 2>&1 || { echo "curl is required to fetch actionlint"; return 1; }
  mkdir -p "$CACHE_DIR"
  curl -fsSL -o "${CACHE_DIR}/${asset}" "${ACTIONLINT_BASE}/${asset}" || {
    echo "download failed: ${ACTIONLINT_BASE}/${asset}"
    return 1
  }
  got="$(sha256sum "${CACHE_DIR}/${asset}" | awk '{print $1}')"
  if [ "$got" != "$sha" ]; then
    echo "checksum mismatch for ${asset}"
    echo "  expected $sha"
    echo "  got      $got"
    rm -f "${CACHE_DIR}/${asset}"
    return 1
  fi
  tar -xzf "${CACHE_DIR}/${asset}" -C "$CACHE_DIR" actionlint
  mv "${CACHE_DIR}/actionlint" "$BIN"
  chmod +x "$BIN"
  rm -f "${CACHE_DIR}/${asset}"
  echo "fetched actionlint ${ACTIONLINT_VERSION} (sha256 verified)"
}

if [ ! -x "$BIN" ]; then
  download_actionlint || FAIL=1
fi

if [ "$FAIL" = "0" ]; then
  echo "actionlint: $("$BIN" --version | head -n 1)"
  echo "checking workflows in ${WORKFLOW_DIR}/"
  "$BIN" || FAIL=1
fi

echo
if [ "$FAIL" = "0" ]; then
  echo "RESULT: PASS (exit 0) - all workflow configuration checks clean"
else
  echo "RESULT: FAIL (exit 1) - CI configuration errors above"
fi
exit "$FAIL"
