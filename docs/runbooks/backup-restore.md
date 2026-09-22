# Backup & Restore Runbook

Last verified: 4bab0f0

This runbook documents what backup actually exists today and, just as
importantly, what does not. Facts are quoted from
`.github/workflows/deploy.yml` and the drill scripts in `backend/scripts/` at
commit `4bab0f0`.

## What exists today: the pre-deploy dump

The only automatic backup is the **pre-deploy dump**, taken inside the deploy
job on every production deploy. From `deploy.yml`, verbatim:

```bash
mkdir -p "$HOME/backups"
$C exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "$HOME/backups/pre-deploy-$(date +%Y%m%d-%H%M%S).sql.gz"
ls -t "$HOME"/backups/pre-deploy-*.sql.gz | tail -n +8 | xargs -r rm --
```

Properties (all verifiable from those two lines):

- **Where:** on the VM, in `$HOME/backups/` (`~/backups/`).
- **Name:** `pre-deploy-YYYYMMDD-HHMMSS.sql.gz` (timestamped).
- **Format:** `pg_dump` piped through `gzip` (a compressed plain SQL dump).
- **When:** once per deploy, after `docker compose ... pull` and before
  `prestart.sh` / `alembic upgrade head`. So it captures the DB state *before*
  migrations run.
- **Retention:** the `ls -t "$HOME"/backups/pre-deploy-*.sql.gz | tail -n +8 |
  xargs -r rm --` line keeps the **7 most recent** dumps and deletes the rest
  (the 8th and older are removed). This logic **does** exist in `deploy.yml`
  exactly as quoted above.

To list and pick a dump on the VM:

```bash
ls -t ~/backups/pre-deploy-*.sql.gz
```

## What does NOT exist yet (known gaps)

These are **known gaps, not working features**:

1. **No independent nightly backup schedule.** There is no cron job, scheduled
   workflow, or timer anywhere in the repo that takes a backup. The only backup
   is the pre-deploy dump, so a database with no recent deploys has no recent
   backup. (Verified: no `cron`/`crontab`/`schedule:`-triggered backup job
   exists in `.github/workflows/` or repo scripts.)
2. **No off-VM copy automation.** The pre-deploy dump is written to `$HOME`
   **on the same VM** as the database. Nothing copies it to object storage, a
   separate host, or any off-site location. A VM/disk loss loses both the DB and
   its backups.
3. **No restore drill has been run.** The repo *contains* two drill scripts
   (see below), but neither is referenced by CI or scheduled anywhere, and there
   is no log or record in the repo of a drill actually being executed.
4. **Only 7 dumps retained.** The pre-deploy dumps are short-lived by design;
   they are not a long-term archive.

> **NEEDS HUMAN REVIEW:** The claim "no restore drill has been run" cannot be
> fully proven from the repo alone — absence of a record is not proof it never
> happened. Confirm with the team whether any manual drill has been executed.
> What *is* verifiable: the drill scripts exist, are not wired into CI, and
> have no scheduled trigger.

## Drill scripts that exist (but are not automated or scheduled)

Two scripts exist that could be used to test a restore:

1. `backend/scripts/backup-restore-drill.sh` — "Backend Phase B7 —
   Backup/Restore Drill". It:
   - dumps the current DB to `backend/backups/drill_dump_<timestamp>.sql`
     (`pg_dump ... --clean --if-exists --no-owner --no-privileges`),
   - fails if the dump is under 1024 bytes,
   - drops/creates a throwaway DB `hris_backup_drill`,
   - restores the dump into it, counts `public` tables
     (`information_schema.tables`), and fails if fewer than 10,
   - prints `DRILL PASSED: ...` and drops the throwaway DB.

2. `backend/scripts/migration/backup_restore_drill.sh` — "B7 —
   Backup/restore drill script". It dumps to `DRILL_DIR` (default
   `/var/backups/hris-drills`), restores into a temp DB, runs row-count
   checksums via `backend/scripts/migration/validate_checksum.py` (note: that
   checker compares against a legacy MySQL source, and its call is suffixed
   `|| true`, so failure is non-fatal), then drops the temp DB.

Neither script is referenced in `.github/workflows/` and neither runs on a
schedule.

## Manual restore

To restore a pre-deploy dump, follow the restore procedure in
`docs/runbooks/rollback.md`. That covers the drop/recreate/restore pattern
(grounded in `backend/scripts/backup-restore-drill.sh`) and how to pin the app
to a matching image tag. Remember:

- The pre-deploy dump is **gzip-compressed** (`*.sql.gz`), while the drill
  scripts restore plain `.sql` files. Decompress first (e.g. `gunzip -c`) —
  verify the exact command before running against production.
- Restoring **overwrites current data**. Take a fresh dump of the live state
  first if you may need the data written since the dump.
- A dump has a `pg_dump` timestamp consistent with the schema *at that deploy*.
  Do not run `alembic upgrade head` against a freshly restored old dump until
  you re-deploy a release whose migrations match.

## Recommended follow-ups (not yet implemented)

- Add a scheduled (e.g. nightly) `pg_dump` job independent of deploys.
- Copy dumps off the VM (object storage or another host) and add a retention
  policy there.
- Wire one of the existing drill scripts into CI or a schedule and record
  results, so a real restore is proven periodically rather than assumed.