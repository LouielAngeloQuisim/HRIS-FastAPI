# Migrations Runbook

Last verified: 4bab0f0

This runbook documents how database migrations actually run in this repo, the
known downgrade trap in migration `b9748b3e7b5c`, and a pre-merge dry-run
process. Facts are quoted from `backend/scripts/prestart.sh`,
`.github/workflows/deploy.yml`, and the files in `backend/alembic/versions/` at
commit `4bab0f0`.

## How migrations run in production

Migrations are NOT run as a separate step in the deploy job. They run inside
`prestart.sh`, which the deploy job invokes before bringing containers up. From
`deploy.yml`:

```bash
$C run --rm -T --no-deps backend bash scripts/prestart.sh
```

`backend/scripts/prestart.sh` (verbatim):

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

Order on every deploy: (1) wait for the DB, (2) `alembic upgrade head`, (3)
seed initial data, (4) `docker compose ... up -d`. The pyproject pins
`alembic<2.0.0,>=1.12.1`.

## Current migration inventory

`backend/alembic/versions/` holds **23** migration files. The chain around the
known-trap migration is:

```
c085a769992a  add_rbac_approve_admin_columns
   └─ b9748b3e7b5c  add_leave_holiday_tables_phase_b3      <-- known trap
        └─ d4b4a4d0b4a1  add_payroll_bracket_and_integration_tables
             └─ d5b5b4e1b4a2  add_missing_payroll_table_indexes
                  └─ f176e167c8e7  change_employee_salary_unique
                       └─ 3009113137ba  add_notification_and_audit_log_tables
                            └─ bc349a74ea22  add_notification_and_audit_log_tables
                                 └─ 9c7a54c3b67f  add_is_deleted_to_audit_log
                                      └─ cc9df25cd8ed  add_is_readonly_to_payroll_tables
                                           └─ a1b2c3d4e5f6  add_pre_payday_notification_type
                                                └─ 54ff6e36652b  add_payroll_tables
                                                     └─ 3f0e3e733925  change_employee_salary_unique (head)
```

`b9748b3e7b5c` is mid-chain, not the head — a real downgrade would also have to
downgrade every migration after it.

## Known trap: `b9748b3e7b5c` downgrade leaves orphaned enum types

`b9748b3e7b5c_add_leave_holiday_tables_phase_b3.py` creates eight PostgreSQL
enum types in `upgrade()`:

```
leavecadence, genderscope, maritalstatusscope,
leavestatus, leaverequesteventtype, leaveledgersource,
holidaytype, observeweekendas
```

Its `downgrade()` (verbatim, lines 209-216) only drops the tables:

```python
def downgrade():
    op.drop_table('holiday_instance')
    op.drop_table('holiday_config')
    op.drop_table('leave_ledger_entry')
    op.drop_table('leave_request_event')
    op.drop_table('leave_request')
    op.drop_table('employee_leave_enrollment')
    op.drop_table('leave_policy')
```

It does **not** `DROP TYPE` the eight enums it created. PostgreSQL does not drop
a type automatically when the table using it is dropped, so after
`alembic downgrade` the enums remain. A subsequent `alembic upgrade head`
re-runs `op.create_table(..., sa.Enum(..., name='leavecadence'), ...)` and fails
because the type already exists.

For contrast, `bc349a74ea22_add_notification_and_audit_log_tables.py` does clean
up after itself in `downgrade()`:

```python
op.execute('DROP TYPE notificationtype')
```

**Consequence: `alembic downgrade` is NOT a safe rollback path for a release
that has run `b9748b3e7b5c` (or any later migration).** Restoring the pre-deploy
dump is the only reliable rollback. See the Rollback runbook.

> **NEEDS HUMAN REVIEW:** confirm whether a forward-only hotfix (manually
> dropping the orphaned enums, or adding the missing `DROP TYPE` in a new
> migration) is acceptable, and whether `b9748b3e7b5c.downgrade()` should be
> patched in a new migration. Do not hand-edit an already-applied migration.

## Pre-merge dry-run process (proposed — not automated)

> **NEEDS HUMAN REVIEW:** Nothing in the repo automates this dry-run, and it is
> not part of CI (`ci.yml` runs `prestart.sh` then `pytest tests/ -q` against a
> throwaway `postgres:18`, but does not restore a production dump). The steps
> below are a proposed mandatory process, not a documented repo procedure.
> Confirm and then automate it before treating it as required.

Proposed process before merging any migration:

1. **Spin up a scratch Postgres** matching production (`postgres:18`):
   ```bash
   docker run --rm -d --name hris-mig-dryrun -e POSTGRES_USER=app -e POSTGRES_PASSWORD=changethis -e POSTGRES_DB=app -p 5433:5432 postgres:18
   ```
   > **NEEDS HUMAN REVIEW:** the credentials/port above mirror `ci.yml`'s service
   > config (`POSTGRES_USER: app`, `POSTGRES_PASSWORD: changethis`,
   > `POSTGRES_DB: app`); confirm they are the intended scratch values.

2. **Restore a copy of a production dump** into it. Use a
   `~/backups/pre-deploy-*.sql.gz` from the VM (see Backup/Restore runbook).
   The dump is gzip-compressed:
   ```bash
   gunzip -c pre-deploy-<timestamp>.sql.gz | psql -h localhost -p 5433 -U app -d app
   ```

3. **Record row counts before** the upgrade, e.g. via the drill's
   `information_schema` pattern or per-table counts.

4. **Run the migration** with the same command production uses:
   ```bash
   cd backend && alembic upgrade head
   ```

5. **Check row counts after** and compare. The repo ships a row-count/checksum
   checker, `backend/scripts/migration/validate_checksum.py`, which compares
   four tables (`employee_records`, `employee_salary`, `payroll_run`,
   `payroll_entry`) between two databases and prints PASS/FAIL per table. It is
   written for the legacy MySQL → Postgres ETL, so its `--mysql-url` points at
   the legacy source; adapt or use plain `psql` counts for a dump-to-dump check.

6. **Run `alembic check`** to confirm the models match the migrated schema:
   ```bash
   cd backend && alembic check
   ```
   > **NEEDS HUMAN REVIEW:** `alembic check` is a standard alembic command and
   > the pinned alembic (>=1.12.1) supports it, but it is **not currently used
   > anywhere in the repo** (no reference in workflows, scripts, or docs).
   > Confirm it produces no false positives against this model set before
   > making it a required gate.

7. **Tear down the scratch DB.** Note `backend/scripts/backup-restore-drill.sh`
   already performs a dump → restore-into-throwaway-DB → table-count check loop
   (`DRILL_DB="hris_backup_drill"`, requires dump size >= 1024 bytes and >= 10
   restored tables), and can be used as a starting point.

## Rollback rule of thumb

If a migration in the release is `b9748b3e7b5c` or later and something goes
wrong, **restore the pre-deploy dump** rather than running `alembic downgrade`.
The dump restore is covered in `docs/runbooks/rollback.md`.
