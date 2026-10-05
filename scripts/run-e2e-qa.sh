#!/usr/bin/env bash
# Isolated UI QA: reuse the QA PostgreSQL container, own a disposable database.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Refuse a production URL even though the runner always exports loopback URLs.
python3 - <<'PYGUARD'
import os
from urllib.parse import urlsplit
for key, default in [('E2E_BASE_URL', 'http://127.0.0.1:5173'), ('E2E_API_URL', 'http://127.0.0.1:8000/api/v1')]:
    url = urlsplit(os.environ.get(key, default))
    if url.scheme != 'http' or url.hostname not in ('127.0.0.1', 'localhost') or url.username is not None or url.password is not None:
        raise SystemExit('Refusing non-loopback E2E URL')
PYGUARD
for qa_spec in "$@"; do
  if [[ "$qa_spec" == *..* || "$qa_spec" == -* || ! -e "$ROOT/frontendv3/e2e/$qa_spec" ]]; then
    echo 'Pass only an existing path relative to frontendv3/e2e' >&2; exit 2
  fi
done
if ! command -v docker >/dev/null; then
  if [[ -x '/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe' ]]; then
    docker() { '/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe' "$@"; }
  else
    echo 'Docker CLI is unavailable; enable Docker Desktop WSL integration' >&2; exit 2
  fi
fi
qa_workers="${E2E_WORKERS:-1}"
[[ "$qa_workers" =~ ^[1-4]$ ]] || { echo 'E2E_WORKERS must be an integer from 1 to 4' >&2; exit 2; }
qa_command_timeout="${E2E_COMMAND_TIMEOUT_SECONDS:-600}"
[[ "$qa_command_timeout" =~ ^[1-9][0-9]*$ ]] && (( qa_command_timeout <= 900 )) || {
  echo 'E2E_COMMAND_TIMEOUT_SECONDS must be an integer from 1 to 900' >&2; exit 2;
}
qa_suite_timeout="${E2E_SUITE_TIMEOUT_SECONDS:-1500}"
[[ "$qa_suite_timeout" =~ ^[1-9][0-9]*$ ]] && (( qa_suite_timeout <= 2400 )) || {
  echo 'E2E_SUITE_TIMEOUT_SECONDS must be an integer from 1 to 2400' >&2; exit 2;
}
command -v uv >/dev/null
command -v pnpm >/dev/null
command -v setsid >/dev/null
command -v flock >/dev/null
command -v timeout >/dev/null
exec 9>/tmp/hris-ui-qa-e2e.lock
flock -n 9 || { echo 'Another isolated QA runner is active' >&2; exit 2; }
# Own these listener ports; never reuse an unknown backend or frontend.
python3 - <<'PY'
import socket
for port in (8000, 5173):
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            listener.bind(('127.0.0.1', port))
        except OSError:
            raise SystemExit(f'QA port {port} is busy; stop its owner before running QA')
PY
qa_created=0
qa_started=0
qa_database_created=0
qa_cleanup_error=0
qa_command_pid=""
qa_database="hris_qa_$(python3 -c 'import secrets; print(secrets.token_hex(6))')"
qa_run_id="$(date -u +%Y%m%dT%H%M%SZ)-$$"
export E2E_RUN_ID="$qa_run_id"
qa_logs="$(mktemp -d /tmp/hris-ui-qa-XXXXXX)"
# Stop the owned session, including descendants that outlive its leader.
qa_stop_group() {
  local group_pid="$1"
  kill -TERM -- "-$group_pid" 2>/dev/null || true
  for _ in {1..20}; do
    kill -0 -- "-$group_pid" 2>/dev/null || break
    sleep 0.1
  done
  kill -KILL -- "-$group_pid" 2>/dev/null || true
  wait "$group_pid" 2>/dev/null || true
}
qa_run_command() {
  local command_timeout="$1"
  shift
  setsid timeout --signal=TERM --kill-after=10 "$command_timeout" "$@" &
  qa_command_pid=$!
  local rc=0
  wait "$qa_command_pid" || rc=$?
  qa_stop_group "$qa_command_pid"
  qa_command_pid=""
  return "$rc"
}
cleanup() {
  local original_status=$?
  trap - EXIT INT TERM
  set +e
  if [[ -n "$qa_command_pid" ]]; then qa_stop_group "$qa_command_pid"; fi
  if [[ -n "${qa_vite_pid:-}" ]]; then qa_stop_group "$qa_vite_pid"; fi
  if [[ -n "${qa_backend_pid:-}" ]]; then qa_stop_group "$qa_backend_pid"; fi
  if [[ "$qa_database_created" == 1 ]]; then
    docker exec hris-ui-qa-e2e psql -U e2e -d e2e -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS $qa_database WITH (FORCE)" >/dev/null 2>&1 || {
      echo "QA cleanup failed: could not drop this run's database $qa_database" >&2
      qa_cleanup_error=1
    }
  fi
  if [[ "$qa_created" == 1 ]]; then
    docker rm -f hris-ui-qa-e2e >/dev/null 2>&1 || { echo 'QA cleanup failed: could not remove the QA container created by this run' >&2; qa_cleanup_error=1; }
  elif [[ "$qa_started" == 1 ]]; then
    docker stop hris-ui-qa-e2e >/dev/null 2>&1 || { echo 'QA cleanup failed: could not restore the QA container to its prior stopped state' >&2; qa_cleanup_error=1; }
  fi
  echo "QA server logs: $qa_logs"
  if [[ "$qa_cleanup_error" == 1 && "$original_status" == 0 ]]; then original_status=1; fi
  exit "$original_status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
if ! docker inspect hris-ui-qa-e2e >/dev/null 2>&1; then
  docker run -d --name hris-ui-qa-e2e -p 127.0.0.1:55603:5432 -e POSTGRES_USER=e2e -e POSTGRES_PASSWORD=e2e-db-placeholder -e POSTGRES_DB=e2e postgres:18 >/dev/null
  qa_created=1
else
  qa_image="$(docker inspect hris-ui-qa-e2e --format '{{.Config.Image}}' | tr -d '\r')"
  [[ "$qa_image" == postgres:18 ]] || { echo 'Unexpected QA database image' >&2; exit 2; }
  if [[ "$(docker inspect hris-ui-qa-e2e --format '{{.State.Running}}' | tr -d '\r')" != true ]]; then
    docker start hris-ui-qa-e2e >/dev/null
    qa_started=1
  fi
fi
qa_db_ready=0
for qa_attempt in $(seq 1 30); do
  if docker exec hris-ui-qa-e2e pg_isready -U e2e -d e2e >/dev/null 2>&1; then qa_db_ready=1; break; fi
  sleep 1
done
[[ "$qa_db_ready" == 1 ]] || { echo 'QA database did not become ready within 30 seconds' >&2; exit 1; }
export ENVIRONMENT=local PROJECT_NAME=HRIS-E2E SECRET_KEY=e2e-placeholder-not-a-real-secret
export FIRST_SUPERUSER=admin@example.com FIRST_SUPERUSER_PASSWORD=e2e-admin-placeholder EMAILS_FROM_EMAIL=info@example.com
export POSTGRES_SERVER=127.0.0.1 POSTGRES_PORT=55603 POSTGRES_USER=e2e POSTGRES_DB="$qa_database"
qa_container_env="$(docker inspect hris-ui-qa-e2e --format '{{range .Config.Env}}{{println .}}{{end}}' | tr -d '\r')"
grep -qx 'POSTGRES_USER=e2e' <<<"$qa_container_env" || { echo 'QA container must use POSTGRES_USER=e2e' >&2; exit 2; }
grep -qx 'POSTGRES_DB=e2e' <<<"$qa_container_env" || { echo 'QA container must use POSTGRES_DB=e2e' >&2; exit 2; }
export POSTGRES_PASSWORD="$(sed -n 's/^POSTGRES_PASSWORD=//p' <<<"$qa_container_env")"
[[ -n "$POSTGRES_PASSWORD" ]] || { echo 'QA container has no configured POSTGRES_PASSWORD' >&2; exit 2; }
export LOGIN_RATE_LIMIT_ATTEMPTS=1000 E2E_SEED_ALLOWED=true E2E_EXTERNAL_SERVERS=true
export BACKEND_CORS_ORIGINS='["http://127.0.0.1:5173"]' FRONTEND_HOST=http://127.0.0.1:5173
export E2E_BASE_URL=http://127.0.0.1:5173 E2E_API_URL=http://127.0.0.1:8000/api/v1 VITE_API_URL=http://127.0.0.1:8000
export E2E_ADMIN_EMAIL=admin@example.com E2E_ADMIN_PASSWORD=e2e-admin-placeholder E2E_USER_EMAIL=user@example.com E2E_USER_PASSWORD=e2e-user-placeholder
export LD_LIBRARY_PATH="$ROOT/frontendv3/.playwright-libs/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
qa_database_created=1
docker exec hris-ui-qa-e2e psql -U e2e -d e2e -v ON_ERROR_STOP=1 -c "CREATE DATABASE $qa_database" >/dev/null
cd "$ROOT/backend"
export PYTHONPATH="$ROOT/backend"
qa_run_command "$qa_command_timeout" uv run bash scripts/prestart.sh
qa_run_command "$qa_command_timeout" uv run python scripts/seed_e2e.py
setsid uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 >"$qa_logs/backend.log" 2>&1 &
qa_backend_pid=$!
cd "$ROOT/frontendv3"
setsid pnpm exec vite --host 127.0.0.1 >"$qa_logs/vite.log" 2>&1 &
qa_vite_pid=$!
qa_ready=0
for qa_attempt in $(seq 1 60); do
  if curl --silent --fail --max-time 2 "$E2E_API_URL/utils/health-check/" >/dev/null && curl --silent --fail --max-time 2 "$E2E_BASE_URL" >/dev/null; then qa_ready=1; break; fi
  sleep 1
done
[[ "$qa_ready" == 1 ]] || { echo "QA servers did not start within 60 seconds; inspect $qa_logs" >&2; exit 1; }
qa_specs=()
for qa_spec in "$@"; do qa_specs+=("e2e/$qa_spec"); done
echo "Playwright workers=$qa_workers retries=0 suite_timeout=${qa_suite_timeout}s run_id=$E2E_RUN_ID"
qa_run_command "$qa_suite_timeout" pnpm exec playwright test "${qa_specs[@]}" --project=chromium --workers="$qa_workers" --retries=0
