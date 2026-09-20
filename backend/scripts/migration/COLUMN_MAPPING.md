# B6 — Legacy MySQL → Postgres Column Mapping

## Source: legacy_hris (MySQL)

| Legacy Table | Legacy Column | Target Table | Target Column | Notes |
|---|---|---|---|---|
| employee | id | employee_records | id | UUID preserved |
| employee | employee_code | employee_records | employee_code | varchar(255) |
| employee | first_name | employee_records | first_name | varchar(255) |
| employee | last_name | employee_records | last_name | varchar(255) |
| employee | birthdate | employee_records | birthdate | date |
| employee | employment_type | employee_records | employment_type | varchar(50) |
| employee | employee_status | employee_records | employee_status | varchar(50) |
| employee | date_hired | employee_records | date_hired | date |
| employee_salary | id | employee_salary | id | UUID preserved |
| employee_salary | employee_id | employee_salary | employee_id | FK → employee_records.id |
| employee_salary | basic_rate | employee_salary | basic_rate | numeric(12,2) |
| employee_salary | currency | employee_salary | currency | char(3), default PHP |
| employee_salary | effective_date | employee_salary | effective_date | date |
| employee_salary | pay_type | employee_salary | pay_type | enum: monthly/daily/hourly |
| employee_salary | overtime_rate | employee_salary | overtime_rate | numeric(6,3) |
| employee_salary | absent_penalty_rate | employee_salary | absent_penalty_rate | numeric(6,3) |
| employee_salary | non_taxable_allowance | employee_salary | non_taxable_allowance | numeric(12,2) |
| payroll_run | id | payroll_run | id | UUID preserved |
| payroll_run | cutoff_type | payroll_run | cutoff_type | enum |
| payroll_run | date_from | payroll_run | date_from | date |
| payroll_run | date_to | payroll_run | date_to | date |
| payroll_run | status | payroll_run | status | enum: draft/approved/paid/void |
| payroll_run | created_by | payroll_run | created_by | FK → user.id |
| payroll_entry | id | payroll_entry | id | UUID preserved |
| payroll_entry | payroll_run_id | payroll_entry | payroll_run_id | FK → payroll_run.id |
| payroll_entry | employee_id | payroll_entry | employee_id | FK → employee_records.id |
| payroll_entry | basic_rate | payroll_entry | basic_rate | numeric(12,2) |
| payroll_entry | gross_pay | payroll_entry | gross_pay | numeric(12,2) |
| payroll_entry | total_deductions | payroll_entry | total_deductions | numeric(12,2) |
| payroll_entry | net_pay | payroll_entry | net_pay | numeric(12,2) |

## Transform Rules

1. **Enum values:** MySQL stored enum labels as strings; Postgres uses the same labels, so no transform needed.
2. **Soft deletes:** Legacy `deleted_at IS NOT NULL` rows map to `is_deleted=True` in the new schema.
3. **UUIDs:** Legacy integer PKs are remapped to UUIDs via the ETL script's lookup tables.
4. **Dates:** MySQL `DATETIME` columns that carry only a date value are cast to `DATE` in Postgres.
5. **JSON fields:** Legacy `TEXT` columns storing JSON dicts (earnings, deductions) are inserted as `JSONB`.

## Validation

After migration, run:
```
python scripts/migration/validate_checksum.py --mysql-url ... --pg-url ...
```

Expected output: `PASS` with matching row counts and checksums for every table.
