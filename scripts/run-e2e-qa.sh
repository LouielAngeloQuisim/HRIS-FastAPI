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
command -v uv >/dev/null
command -v pnpm >/dev/null
command -v setsid >/dev/null
command -v flock >/dev/null
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
qa_database="hris_qa_$(python3 -c 'import secrets; print(secrets.token_hex(6))')"
qa_logs="$(mktemp -d /tmp/hris-ui-qa-XXXXXX)"
cleanup() {
  if [[ -n "${qa_vite_pid:-}" ]]; then kill -- "-$qa_vite_pid" 2>/dev/null || true; fi
  if [[ -n "${qa_backend_pid:-}" ]]; then kill -- "-$qa_backend_pid" 2>/dev/null || true; fi
  docker exec hris-ui-qa-e2e psql -U e2e -d e2e -c "DROP DATABASE IF EXISTS $qa_database WITH (FORCE)" >/dev/null 2>&1 || true
  if [[ "$qa_created" == 1 ]]; then docker rm -f hris-ui-qa-e2e >/dev/null 2>&1 || true
  elif [[ "$qa_started" == 1 ]]; then docker stop hris-ui-qa-e2e >/dev/null 2>&1 || true; fi
  echo "QA server logs: $qa_logs"
}
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
trap cleanup EXIT
for qa_attempt in $(seq 1 30); do
  if docker exec hris-ui-qa-e2e pg_isready -U e2e -d e2e >/dev/null 2>&1; then break; fi
  sleep 1
done
export ENVIRONMENT=local PROJECT_NAME=HRIS-E2E SECRET_KEY=e2e-placeholder-not-a-real-secret
export FIRST_SUPERUSER=admin@example.com FIRST_SUPERUSER_PASSWORD=e2e-admin-placeholder EMAILS_FROM_EMAIL=info@example.com
export POSTGRES_SERVER=127.0.0.1 POSTGRES_PORT=55603 POSTGRES_USER=e2e POSTGRES_DB="$qa_database"
export POSTGRES_PASSWORD="$(docker inspect hris-ui-qa-e2e --format '{{range .Config.Env}}{{println .}}{{end}}' | sed -n 's/^POSTGRES_PASSWORD=//p' | tr -d '\r')"
export LOGIN_RATE_LIMIT_ATTEMPTS=1000 E2E_SEED_ALLOWED=true E2E_EXTERNAL_SERVERS=true
export BACKEND_CORS_ORIGINS='["http://127.0.0.1:5173"]' FRONTEND_HOST=http://127.0.0.1:5173
export E2E_BASE_URL=http://127.0.0.1:5173 E2E_API_URL=http://127.0.0.1:8000/api/v1 VITE_API_URL=http://127.0.0.1:8000
export E2E_ADMIN_EMAIL=admin@example.com E2E_ADMIN_PASSWORD=e2e-admin-placeholder E2E_USER_EMAIL=user@example.com E2E_USER_PASSWORD=e2e-user-placeholder
export LD_LIBRARY_PATH="$ROOT/frontendv3/.playwright-libs/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
docker exec hris-ui-qa-e2e psql -U e2e -d e2e -c "CREATE DATABASE $qa_database" >/dev/null
cd "$ROOT/backend"
export PYTHONPATH="$ROOT/backend"
uv run bash scripts/prestart.sh
uv run python scripts/seed_e2e.py
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
[[ "$qa_ready" == 1 ]] || { echo "QA servers did not start; inspect $qa_logs" >&2; exit 1; }
qa_specs=()
for qa_spec in "$@"; do qa_specs+=("e2e/$qa_spec"); done
pnpm exec playwright test "${qa_specs[@]}" --project=chromium --workers=1 --retries=0 --reporter=line
