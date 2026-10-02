# Known migration rollback limitations

The normal deployment path runs alembic upgrade head and checks drift. A green upgrade does not prove every historical downgrade is safe.

Repository-recorded throwaway PostgreSQL 18 experiments on 2026-09-30 found:

| Revision | Limitation |
| --- | --- |
| 7286295e0903 | Downgrade leaves employeestatus behind; re-upgrade fails with DuplicateObject |
| b9748b3e7b5c | Downgrade leaves eight leave-domain enum types behind; re-upgrade fails with DuplicateObject for leavecadence |
| d4b4a4d0b4a1 | Downgrade leaves payroll enum types behind; re-upgrade fails with DuplicateObject for cutofftype |
| 10fc690ffb09 | An unnamed foreign-key drop fails with CompileError before downgrade completes |

Source evidence and exact failure descriptions: [ROADMAP #52](../ROADMAP.md). These are historical reproduced results, not new production experiments.

Do not run those downgrade paths on production as a rollback shortcut. Preserve the chain per the owner's 2026-10-02 decision. Follow [rollback](rollback.md) and [backup/restore](backup-restore.md) using a compatible application image and pre-deployment backup. Restore only through the runbook's authorized maintenance procedure, then validate schema/application compatibility and deployment health.

The salary-constraint chain f176e167c8e7 -> 54ff6e36652b -> 3f0e3e733925 produces the intended employee_id/effective_date uniqueness at head. It is preserved rather than cosmetically rewritten. New migrations must explicitly clean up native enums when appropriate and pass upgrade/downgrade/re-upgrade checks on a disposable database.
