# Audit retention
Owner decision (2026-10-02): retain 90 days; deletion disabled until explicitly enabled.
The audit-retention Compose service uses the backend image and runs daily.
AUDIT_RETENTION_ENABLED defaults to false. Dry runs report only the capped
eligible count, never audit records or database exception details.
Set AUDIT_RETENTION_ENABLED=true in production configuration only after
reviewing the cutoff and confirming backups. No production enablement is part
of this change. AUDIT_RETENTION_DAYS defaults to 90; AUDIT_RETENTION_BATCH_SIZE
defaults to 1000. Each daily run deletes at most that many records strictly
older than the cutoff, including soft-deleted records. Boundary records,
newer records and records with null timestamps are retained.
Large backlogs require repeated runs or a reviewed batch-size adjustment.
To run once in the backend container: python -m app.audit.retention.
Scheduled mode: python -m app.audit.retention --scheduled.
The job commits each successful batch; failure is logged without row values.
A single Compose service runs the job, independent of API worker count.
