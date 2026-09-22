# Rollback Runbook

Last verified: 4bab0f0

This runbook documents how to roll back a production deploy. Commands are
grounded in `compose.prod.yml`, `.github/workflows/deploy.yml`, and the backup
drill script `backend/scripts/backup-restore-drill.sh` at commit `4bab0f0`.
Where a step is operational guidance rather than something quoted verbatim from
the repo, it is marked **NEEDS HUMAN REVIEW**.

## When to roll back vs. fix forward

> **NEEDS HUMAN REVIEW:** This section is operational guidance, not a procedure
> quoted from a repo file. Confirm the team's actual policy.

General guidance:

- **Roll back** when the new release is broken in a way that cannot be fixed
  quickly and safely in place (crash loops, data corruption, a bad migration
  that already ran, core flows down). Rollback restores the previous *image*
  and, when a migration changed the schema, the previous *data* (via the
  pre-deploy dump).
- **Fix forward** when the issue is minor and quick to patch (a bad config
  value, a small code bug, a feature flag) and the schema is unchanged. Fixing
  forward avoids the data-loss risk of restoring an older dump on top of new
  writes.

The deciding factor is usually: **did a migration run, and did users write new
data since the deploy?** If yes to either, a full dump restore is riskier and
must be weighed carefully.

## Where dumps are stored

The pipeline takes a pre-deploy dump on every deploy and stores it on the VM at
`~/backups/pre-deploy-*.sql.gz` (i.e. `$HOME/backups/`). From `deploy.yml`:

```bash
mkdir -p "$HOME/backups"
$C exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "$HOME/backups/pre-deploy-$(date +%Y%m%d-%H%M%S).sql.gz"
ls -t "$HOME"/backups/pre-deploy-*.sql.gz | tail -n +8 | xargs -r rm --
```

So: dumps are gzip-compressed SQL, named with a `YYYYMMDD-HHMMSS` timestamp,
and only the **7 most recent** are kept (the `tail -n +8 | xargs -r rm --` line
deletes anything older). List them on the VM:

```bash
ls -t ~/backups/pre-deploy-*.sql.gz
```

Pick the dump taken at the start of the deploy you want to undo (the one
timestamped just before the bad release came up).

## How to find the previous working image tag

Two sources, both verifiable from `deploy.yml`:

1. **`$HOME/.hris_previous_tag`** — the pipeline writes the previously-deployed
   tag here on every deploy. From `deploy.yml` (lines 105-106):

   ```bash
   [ -f "$HOME/.hris_deployed_tag" ] && cp "$HOME/.hris_deployed_tag" "$HOME/.hris_previous_tag" || true
   echo "$IMAGE_TAG" > "$HOME/.hris_deployed_tag"
   ```

   So `.hris_previous_tag` **is** created by `deploy.yml` — but only on the
   *second* and later deploys, because it is copied from `.hris_deployed_tag`,
   which only exists after the first deploy has written it. On a brand-new VM
   the first deploy leaves `.hris_previous_tag` absent. Read it with:

   ```bash
   cat ~/.hris_previous_tag
   ```

2. **`docker images`** — the pipeline tags images with the full commit SHA
   (`${{ github.sha }}`) and `latest`. To list the candidate tags:

   ```bash
   docker images | grep hris-fastapi
   ```

   > **NEEDS HUMAN REVIEW:** The task suggested `docker images | grep pre-hris`.
   > The string `pre-hris` does NOT appear anywhere in the repo; the real image
   > names are `ghcr.io/louielangeloquisim/hris-fastapi/backend` and
   > `.../frontend` (see `compose.prod.yml`), tagged with the commit SHA or
   > `latest`. Use `docker images | grep hris-fastapi` instead. Confirm the
   > exact tag convention on the VM before relying on a specific grep.

## Rollback procedure

> **NEEDS HUMAN REVIEW:** The assembled production procedure below is not a
> single documented, tested script in the repo. Each individual command is
> grounded in a verifiable file (noted inline), but the *sequence* for a
> production rollback has not been verified end-to-end. Review before executing
> on the live VM, and prefer restoring into a scratch database first (see the
> drill script) to validate the dump.

The drop/recreate/restore pattern is taken from
`backend/scripts/backup-restore-drill.sh` (which does this against a throwaway
database). Adapt it to the production database:

1. **Stop the app services** so they don't write while you restore the DB.
   Grounded in `compose.prod.yml` (services `backend`, `frontend`):

   ```bash
   docker compose -f compose.prod.yml stop backend frontend
   ```

   > **NEEDS HUMAN REVIEW:** confirm whether `stop backend frontend` (vs.
   > `stop`) is the intended scope, and whether traefik should stay up.

2. **Drop and recreate the production database.** The drill script uses
   (quoted from `backend/scripts/backup-restore-drill.sh`):

   ```bash
   psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE IF EXISTS \"$DRILL_DB\";" >/dev/null 2>&1 || true
   psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE \"$DRILL_DB\";" >/dev/null
   ```

   For production, substitute the real production DB name for `$DRILL_DB`.
   > **NEEDS HUMAN REVIEW:** confirm the exact production DB name and whether
   > the recreate must also restore the original owner/privileges (the drill
   > dump uses `--no-owner --no-privileges`).

3. **Restore the chosen dump.** The drill script restores with:

   ```bash
   psql \
       -h "$POSTGRES_HOST" \
       -p "$POSTGRES_PORT" \
       -U "$POSTGRES_USER" \
       -d "$DRILL_DB" \
       -f "$DUMP_FILE" \
       >/dev/null
   ```

   Point `$DUMP_FILE` at the `~/backups/pre-deploy-*.sql.gz` you selected. Note
   the dump is gzip-compressed; the drill restores a plain `.sql`, so confirm
   the decompression step (e.g. `gunzip -c`) for the `.sql.gz` pre-deploy dumps.
   > **NEEDS HUMAN REVIEW:** the drill script writes a plain `.sql`; the
   > pre-deploy dumps are `.sql.gz`. Confirm the exact restore command for a
   > `.sql.gz` file before running it.

4. **Bring the app back up pinned to the previous image tag.** `compose.prod.yml`
   reads the `IMAGE_TAG` env var (default `latest`):

   ```yaml
   image: ghcr.io/louielangeloquisim/hris-fastapi/backend:${IMAGE_TAG:-latest}
   image: ghcr.io/louielangeloquisim/hris-fastapi/frontend:${IMAGE_TAG:-latest}
   ```

   So pin the previous tag (from `~/.hris_previous_tag`) and start:

   ```bash
   IMAGE_TAG=<previous-sha> docker compose -f compose.prod.yml up -d
   ```

   > **NEEDS HUMAN REVIEW:** confirm the exact way the VM's `.env`/compose
   > invocation passes `IMAGE_TAG` (the pipeline exports it in the deploy job;
   > the VM's standing `.env` may or may not set it). Verify the containers
   > come up `healthy` (see the Deploy runbook) before declaring the rollback
   > complete.

## Safety notes

- Restoring an older dump **discards any data written since that dump was
  taken**. Take a fresh dump of the current (broken) state before restoring, so
  you can recover the new writes or investigate later.
- If the rollback is due to a **bad migration**, restoring the dump is the safe
  path — do NOT rely on `alembic downgrade` (see the Migrations runbook for the
  known downgrade trap).
- After restoring, the restored database is at the schema of the *previous*
  release, which matches the previous image. Do not run `alembic upgrade head`
  against the restored DB until you have re-deployed a release whose migrations
  are known-good.
