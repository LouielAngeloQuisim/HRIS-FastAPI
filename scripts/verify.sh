#!/usr/bin/env bash
#
# scripts/verify.sh - single entry point for "does this actually work".
#
# Runs the real backend + frontend checks and prints a PASS/FAIL summary.
# Exit code 0 only when every HARD-GATE check passed. mypy and eslint are
# REPORT-ONLY for now (known pre-existing issues tracked separately).
#
# Safety:
#   * Never touches production, the VM, or any live database.
#   * Backend checks run against a throwaway postgres:18 container on
#     127.0.0.1 with a random free port, created and removed per run.
#   * Backend settings are injected via exported env vars, which
#     pydantic-settings prefers over any repo-root .env. That means this
#     script works on a fresh checkout with no .env (fixes the pytest
#     collect exit-4 problem) AND cannot accidentally hit a developer's
#     real database even if a live .env is present.
#   * If docker is unavailable, DB-dependent backend checks are SKIPPED
#     with a warning instead of failing the whole script (mirrors the
#     "degrade gracefully" decision; everything else still runs).
#
# Usage:  bash scripts/verify.sh   (from anywhere; paths are absolute)

set -u
set -o pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DB_CONTAINER="hris-verify-pg-$$"
DB_PORT=""
DB_READY=0
DB_SKIP_REASON=""

# Result recorder: "STATUS|label|detail"
RESULTS=()
record() { RESULTS+=("$1|$2|$3"); }

section() {
  printf '\n==================================================================\n'
  printf '  %s\n' "$1"
  printf '==================================================================\n'
}

cleanup() {
  if [ -n "$DB_CONTAINER" ]; then
    docker rm -f "$DB_CONTAINER" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

# ---------------------------------------------------------------- backend env
# Same variable set CI's postgres service exposes (see .github/workflows/ci.yml).
export ENVIRONMENT=local
export PROJECT_NAME=HRIS
export SECRET_KEY=verify-script-placeholder-not-a-real-secret
export FIRST_SUPERUSER=admin@example.com
export FIRST_SUPERUSER_PASSWORD=verify-only
export EMAILS_FROM_EMAIL=info@example.com
export POSTGRES_USER=verify
export POSTGRES_PASSWORD=verify
export POSTGRES_DB=verify
export POSTGRES_SERVER=127.0.0.1

# ------------------------------------------------------------- throwaway db
pick_free_port() {
  local p
  for p in 55432 55433 55434 55435 55436 55437 55438 55439 55440; do
    if ! (exec 3<>"/dev/tcp/127.0.0.1/$p") 2>/dev/null; then
      printf '%s' "$p"
      return 0
    fi
  done
  return 1
}

start_throwaway_db() {
  DB_PORT="$(pick_free_port)" || {
    DB_SKIP_REASON="no free TCP port in 55432-55440"
    return 1
  }
  export POSTGRES_PORT="$DB_PORT"

  if ! docker run -d --rm --name "$DB_CONTAINER" \
      -p "127.0.0.1:${DB_PORT}:5432" \
      -e POSTGRES_USER=verify -e POSTGRES_PASSWORD=verify -e POSTGRES_DB=verify \
      postgres:18 >/dev/null 2>&1; then
    DB_SKIP_REASON="docker run postgres:18 failed (is the daemon running and the image pullable?)"
    return 1
  fi

  local i
  for i in $(seq 1 60); do
    if docker exec "$DB_CONTAINER" pg_isready -U verify -d verify >/dev/null 2>&1; then
      DB_READY=1
      return 0
    fi
    sleep 1
  done
  DB_SKIP_REASON="postgres container never became ready within 60s"
  return 1
}

# -------------------------------------------------------------- preflight
section "PREFLIGHT: toolchains + dependencies"
PREFLIGHT_OK=1

command -v uv >/dev/null 2>&1 || { echo "MISSING: uv (install: https://docs.astral.sh/uv/)"; PREFLIGHT_OK=0; }
command -v pnpm >/dev/null 2>&1 || { echo "MISSING: pnpm (install: corepack enable)"; PREFLIGHT_OK=0; }

if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  echo "docker: available -> backend tests will run against a throwaway postgres:18 container"
  start_throwaway_db || { echo "WARNING: throwaway DB not started: $DB_SKIP_REASON"; }
else
  DB_SKIP_REASON="docker not available"
  echo "WARNING: docker not available -> DB-dependent backend checks (alembic, pytest) will be SKIPPED, not failed"
fi

if [ "$PREFLIGHT_OK" = "1" ] && command -v uv >/dev/null 2>&1; then
  echo "--- uv sync (backend deps, idempotent)"
  ( cd backend && uv sync >/dev/null ) || { echo "uv sync failed"; PREFLIGHT_OK=0; }
fi
if [ "$PREFLIGHT_OK" = "1" ] && command -v pnpm >/dev/null 2>&1; then
  echo "--- pnpm install (frontend deps, idempotent)"
  ( cd frontendv3 && pnpm install --frozen-lockfile >/dev/null ) || { echo "pnpm install failed"; PREFLIGHT_OK=0; }
fi

if [ "$PREFLIGHT_OK" != "1" ]; then
  echo
  echo "PREFLIGHT FAILED - install missing toolchains and re-run."
  exit 1
fi

# --------------------------------------------------------------- check 1/8
section "[1/8] backend: ruff check (HARD GATE)"
if ( cd backend && uv run ruff check app ); then
  echo "ruff: clean"
  record PASS "backend/ruff" "clean"
else
  record FAIL "backend/ruff" "lint errors (see output above)"
fi

# --------------------------------------------------------------- check 2/8
section "[2/8] backend: mypy app (REPORT-ONLY known gap)"
MYPY_OUT="$( cd backend && uv run mypy app 2>&1 )" || true
MYPY_COUNT="$(printf '%s\n' "$MYPY_OUT" | grep -cE 'error:' || true)"
printf '%s\n' "$MYPY_OUT" | tail -n 3
echo "mypy error count: ${MYPY_COUNT} (report-only: known pre-existing issues, tracked separately, NOT gating)"
record REPORT "backend/mypy" "${MYPY_COUNT} errors (known gap, not gating)"

# --------------------------------------------------------------- check 3/8
section "[3/8] backend: alembic upgrade head + alembic check (HARD GATE)"
if [ "$DB_READY" = "1" ]; then
  (
    cd backend \
    && uv run python app/backend_pre_start.py >/dev/null \
    && uv run alembic upgrade head \
    && uv run alembic check
  )
  if [ $? -eq 0 ]; then
    echo "alembic: migrations apply cleanly, no model/migration drift"
    record PASS "backend/alembic-check" "no drift"
  else
    record FAIL "backend/alembic-check" "upgrade or check failed (see output above)"
  fi
else
  echo "SKIPPED: no throwaway database (docker unavailable or start failed: ${DB_SKIP_REASON:-unknown})"
  record SKIP "backend/alembic-check" "no DB: ${DB_SKIP_REASON:-unknown}"
fi

# --------------------------------------------------------------- check 4/8
section "[4/8] backend: pytest tests/ -q (HARD GATE)"
if [ "$DB_READY" = "1" ]; then
  PYTEST_OUT="$( cd backend && uv run python app/tests_pre_start.py >/dev/null 2>&1 && uv run pytest tests/ -q 2>&1 )"
  PYTEST_RC=$?
  printf '%s\n' "$PYTEST_OUT" | tail -n 15
  if [ "$PYTEST_RC" -eq 0 ]; then
    SUMMARY="$(printf '%s\n' "$PYTEST_OUT" | grep -E '[0-9]+ (passed|passed,.*|deselected|no tests ran)' | tail -n 1)"
    echo "pytest: green (${SUMMARY})"
    record PASS "backend/pytest" "$SUMMARY"
  else
    FAILED="$(printf '%s\n' "$PYTEST_OUT" | grep -E '[0-9]+ (failed|errors)' | tail -n 1)"
    echo "pytest: FAILED (rc=${PYTEST_RC}) ${FAILED}"
    record FAIL "backend/pytest" "rc=${PYTEST_RC}; ${FAILED:-see output above}"
  fi
else
  echo "SKIPPED: no throwaway database (docker unavailable or start failed: ${DB_SKIP_REASON:-unknown})"
  record SKIP "backend/pytest" "no DB: ${DB_SKIP_REASON:-unknown}"
fi

# --------------------------------------------------------------- check 5/8
section "[5/8] frontend: pnpm exec tsc -b (HARD GATE)"
if ( cd frontendv3 && pnpm exec tsc -b ); then
  echo "tsc: 0 errors"
  record PASS "frontend/tsc" "0 errors"
else
  record FAIL "frontend/tsc" "type errors (see output above)"
fi

# --------------------------------------------------------------- check 6/8
section "[6/8] frontend: pnpm exec eslint . (REPORT-ONLY known gap)"
ESLINT_OUT="$( cd frontendv3 && pnpm exec eslint . 2>&1 )" || true
ESLINT_SUMMARY="$(printf '%s\n' "$ESLINT_OUT" | grep -E 'problems' | tail -n 1)"
printf '%s\n' "$ESLINT_SUMMARY"
echo "eslint: report-only (known no-explicit-any pre-existing errors, NOT gating)"
record REPORT "frontend/eslint" "${ESLINT_SUMMARY:-see tool output} (known gap, not gating)"

# --------------------------------------------------------------- check 7/8
section "[7/8] frontend: vitest run --browser.headless (HARD GATE)"
(
  cd frontendv3
  # Chromium system libs (this host lacks libnss3 et al; see docs/AGENTS.md)
  if [ ! -d ".playwright-libs/usr/lib/x86_64-linux-gnu" ]; then
    echo "--- .playwright-libs missing, running scripts/setup-playwright-libs.sh (one-time, idempotent)"
    bash scripts/setup-playwright-libs.sh >/dev/null 2>&1 || echo "NOTE: playwright lib setup failed; continuing (may be unneeded on this host)"
  fi
  export LD_LIBRARY_PATH="$(pwd)/.playwright-libs/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
  # Browser binary
  if [ ! -d "$HOME/.cache/ms-playwright" ] || [ -z "$(ls "$HOME/.cache/ms-playwright" 2>/dev/null)" ]; then
    echo "--- no playwright browsers found, running: pnpm exec playwright install chromium"
    pnpm exec playwright install chromium || exit 42
  fi
  pnpm exec vitest run --browser.headless
)
VITEST_RC=$?
if [ "$VITEST_RC" -eq 0 ]; then
  record PASS "frontend/vitest" "all tests green"
elif [ "$VITEST_RC" -eq 42 ]; then
  echo "vitest: FAILED - could not install Playwright Chromium."
  echo "HINT: run  cd frontendv3 && pnpm exec playwright install --with-deps chromium  then re-run."
  record FAIL "frontend/vitest" "playwright browser deps missing (see hint)"
else
  record FAIL "frontend/vitest" "rc=${VITEST_RC} (see output above)"
fi

# --------------------------------------------------------------- check 8/8
section "[8/8] frontend: pnpm build (HARD GATE)"
if ( cd frontendv3 && pnpm build >/tmp/verify-build.log 2>&1 ); then
  tail -n 5 /tmp/verify-build.log
  echo "build: OK (full log: /tmp/verify-build.log)"
  record PASS "frontend/build" "ok"
else
  echo "build: FAILED - last 30 lines:"
  tail -n 30 /tmp/verify-build.log
  record FAIL "frontend/build" "see /tmp/verify-build.log"
fi

# ------------------------------------------------------------------ summary
section "SUMMARY"
printf '%-8s %-28s %s\n' "STATUS" "CHECK" "DETAIL"
printf '%-8s %-28s %s\n' "------" "-----" "------"
FINAL=0
for r in "${RESULTS[@]}"; do
  IFS='|' read -r st label detail <<<"$r"
  printf '%-8s %-28s %s\n' "$st" "$label" "$detail"
  case "$st" in
    FAIL) FINAL=1 ;;
    SKIP) echo "        ^ WARNING: skipped, not passed. Final claim of 'verified' must note this." ;;
  esac
done
echo
if [ "$FINAL" -eq 0 ]; then
  if [ "$DB_READY" = "1" ]; then
    echo "RESULT: PASS (exit 0) - all hard gates green, backend checks ran against throwaway container ${DB_CONTAINER}"
  else
    echo "RESULT: PASS (exit 0) for checks that ran, but backend DB checks were SKIPPED (${DB_SKIP_REASON:-unknown}). Do not claim full verification."
  fi
else
  echo "RESULT: FAIL (exit 1) - at least one hard gate failed; see per-check sections above"
fi
exit "$FINAL"
