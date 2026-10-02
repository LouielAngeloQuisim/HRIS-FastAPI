# Preserve migration history and document rollback limits

Date: 2026-10-02. The owner explicitly chose to preserve the existing migration chain and document tested rollback limitations for roadmap #52/#78.

The upgrade path is the supported deployment path and passes Alembic's drift check. Do not cosmetically squash or rewrite deployed revisions. Salary-constraint revisions f176e167c8e7, 54ff6e36652b and 3f0e3e733925 have a correct final schema with one head; preserve their provenance.

Known downgrade/re-upgrade failures are documented in [migration limitations](../runbooks/migration-limitations.md). The reproduced failure evidence was recorded in ROADMAP on 2026-09-30; this decision does not claim those experiments were repeated on 2026-10-02. Use the backup/restore rollback procedure for a deployment requiring database rollback. Future migrations must be round-trip tested on a disposable database.
