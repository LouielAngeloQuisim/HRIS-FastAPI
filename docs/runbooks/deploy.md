# Deploy Runbook

Last verified: 4bab0f0

This runbook documents the production deploy pipeline exactly as it appears in
`.github/workflows/deploy.yml` (workflow name: `Build and Deploy`) and
`compose.prod.yml`. Every command below is quoted from those files at commit
`4bab0f0`.

## What triggers a deploy

The workflow is triggered by a push to `main` (typically via a merged PR) or by
manual dispatch. From `deploy.yml`:

```yaml
on:
  push:
    branches: [main]
    paths-ignore:
      - docs/**
      - analysis/**
      - .kilo/**
      - '**/*.md'
  workflow_dispatch:
```

Note the `paths-ignore`: pushes that only touch `docs/`, `analysis/`, `.kilo/`,
or any `*.md` file do NOT trigger a deploy.

Concurrency is serialized so deploys never overlap:

```yaml
concurrency:
  group: deploy
  cancel-in-progress: false
```

## Job sequence

The jobs run in this order (each `needs` the previous):

1. `ci` — runs the reusable workflow `./.github/workflows/ci.yml`
   (frontend: tsc, eslint, vitest browser, build; backend: prestart,
   tests_pre_start, `pytest tests/ -q` against a postgres:18 service).
2. `build-and-push` — `needs: ci`, gated on `if: github.ref == 'refs/heads/main'`.
   Builds and pushes two images to GHCR, each tagged `latest` and `${{ github.sha }}`:
   - backend: `./backend/Dockerfile`
   - frontend: `./frontendv3/Dockerfile` (build-arg `VITE_API_URL=https://api.hrisly.duckdns.org`)
3. `deploy` — `needs: build-and-push`. Runs the SSH script below on the VM.
4. `verify` — `needs: deploy`. Curls the live API and frontend until both return 200.

## What the deploy job does, step by step

The `deploy` job is a single step, `Deploy to VM via SSH`, using
`appleboy/ssh-action@v1.0.3` with host/user/key from the secrets
`VM_HOST`, `VM_USER`, `VM_SSH_KEY`. The script (quoted verbatim from
`deploy.yml`) is:

```bash
set -euo pipefail
cd ${{ secrets.VM_PROJECT_PATH }}
git pull origin main
echo "${{ secrets.GITHUB_TOKEN }}" | docker login ghcr.io -u ${{ github.actor }} --password-stdin
export IMAGE_TAG=${{ github.sha }}
C="docker compose -f compose.prod.yml"
$C pull
mkdir -p "$HOME/backups"
$C exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "$HOME/backups/pre-deploy-$(date +%Y%m%d-%H%M%S).sql.gz"
ls -t "$HOME"/backups/pre-deploy-*.sql.gz | tail -n +8 | xargs -r rm --
$C run --rm -T --no-deps backend bash scripts/prestart.sh
$C up -d --remove-orphans
cid=$($C ps -q backend)
s=starting
for i in $(seq 1 36); do s=$(docker inspect -f '{{.State.Health.Status}}' "$cid"); [ "$s" = healthy ] && break; sleep 5; done
[ "$s" = healthy ] || { $C logs --tail 60 backend; exit 1; }
[ -f "$HOME/.hris_deployed_tag" ] && cp "$HOME/.hris_deployed_tag" "$HOME/.hris_previous_tag" || true
echo "$IMAGE_TAG" > "$HOME/.hris_deployed_tag"
docker image prune -f
```

Step by step:

1. **pull** — `git pull origin main` in the VM project path
   (`${{ secrets.VM_PROJECT_PATH }}`).
2. **docker login** — logs into GHCR with the workflow's `GITHUB_TOKEN`.
3. **pin tag** — `export IMAGE_TAG=${{ github.sha }}` so compose pulls the exact
   commit's image, not `latest`.
4. **pull images** — `$C pull` (i.e. `docker compose -f compose.prod.yml pull`).
5. **pre-deploy dump** — `mkdir -p "$HOME/backups"` then
   `$C exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip >
   "$HOME/backups/pre-deploy-$(date +%Y%m%d-%H%M%S).sql.gz"`. This is the only
   automatic backup; it is taken on every deploy, before migration.
6. **prune old dumps** — `ls -t "$HOME"/backups/pre-deploy-*.sql.gz | tail -n +8
   | xargs -r rm --` keeps the 7 most recent `pre-deploy-*.sql.gz` files and
   deletes anything older.
7. **prestart / migrate** — `$C run --rm -T --no-deps backend bash
   scripts/prestart.sh`. `prestart.sh` (quoted verbatim) is:

   ```bash
   #! /usr/bin/env bash

   set -e
   set -x

   # Let the DB start
   python app/backend_pre_start.py

   # Run migrations
   alembic upgrade head

   # Create initial data in DB
   python app/initial_data.py
   ```

   So migration runs here, via `alembic upgrade head`, before the new containers
   come up.
8. **up** — `$C up -d --remove-orphans`.
9. **health wait** — grabs the backend container id and polls
   `docker inspect -f '{{.State.Health.Status}}'` up to 36 times (5s apart, ~3
   minutes) until it reports `healthy`.
10. **fail on unhealthy** — if still not healthy, dumps `$C logs --tail 60
    backend` and `exit 1`.
11. **record tag** — copies the previous `.hris_deployed_tag` to
    `.hris_previous_tag` (if it exists), then writes the current `$IMAGE_TAG` to
    `.hris_deployed_tag`.
12. **prune images** — `docker image prune -f`.

## What "healthy" looks like

The backend container's healthcheck is defined in `compose.prod.yml`:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/utils/health-check/"]
  interval: 10s
  timeout: 5s
  retries: 5
```

The `db` container healthcheck is:

```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
  interval: 10s
  retries: 5
  start_period: 30s
  timeout: 10s
```

The `GET /api/v1/utils/health-check/` route is public (listed in
`backend/app/common/route_policy.py` and implemented in
`backend/app/user/routes/utils.py`).

## How to check health manually

The `verify` job curls these exact targets, up to 12 times (10s apart), and
succeeds only when both return HTTP 200:

```bash
api_code=$(curl -s -o /dev/null -w '%{http_code}' https://api.hrisly.duckdns.org/api/v1/utils/health-check/)
fe_code=$(curl -s -o /dev/null -w '%{http_code}' https://dashboard.hrisly.duckdns.org/)
```

To check the containers on the VM (the task references `ssh hris-debug ps`), the
equivalent of what the pipeline does is:

```bash
ssh hris-debug "docker compose -f compose.prod.yml ps"
```

> **NEEDS HUMAN REVIEW:** the exact host alias `hris-debug` and the exact
> `docker compose` invocation used for manual checks are not present in
> `deploy.yml` (the pipeline uses the `VM_HOST` secret, not a literal alias).
> Confirm the real SSH alias and project path before relying on this command.

## Manual / bypass deploys

> **NEEDS HUMAN REVIEW:** The task asks this runbook to state that a command
> `hris-deploy deploy` "bypasses this entire pipeline (no dump, no migration)
> and must not be used for deploys with pending migrations." However, the string
> `hris-deploy` does NOT appear anywhere in the repository (searched
> `*.yml`, `*.sh`, `*.md` and all files). Its existence and its "no dump, no
> migration" behavior cannot be verified from the repo files. Do not treat this
> command as confirmed until a human verifies where it is defined and what it
> does. If a manual deploy path does exist, it must still run migrations and
> take a dump before going live when there are pending migrations.

## Image tags

Both services in `compose.prod.yml` pull a tag driven by the `IMAGE_TAG` env
var, defaulting to `latest`:

```yaml
image: ghcr.io/louielangeloquisim/hris-fastapi/backend:${IMAGE_TAG:-latest}
image: ghcr.io/louielangeloquisim/hris-fastapi/frontend:${IMAGE_TAG:-latest}
```

The pipeline sets `IMAGE_TAG` to the full commit SHA (`${{ github.sha }}`), so
production runs the exact commit that was built and pushed.
