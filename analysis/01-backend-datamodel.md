# WCH HRIS — Backend Data Model Reference (Symfony/Doctrine → SQLAlchemy port)

> Source of truth: `/mnt/f/laragon/www/wchhris-api` (analysed read-only).
> Companion frontend (Twig) mined for enum literals: `/mnt/f/laragon/www/wchhris`.
> This document is the **sole schema source of truth** for the SQLAlchemy rewrite.

---

## 1. Overview

### 1.1 Inventory

| Artefact | Count | Location |
|---|---|---|
| Doctrine entities | **58** | `src/Entity/*.php` |
| Controllers | **42** | `src/Controller/*.php` |
| Repositories | **58** (one per entity; only **24** contain custom queries) | `src/Repository/*.php` |
| Doctrine migrations | **4** | `migrations/Version*.php` |
| Services | 6 | `src/Service/` (`AuditLog`, `CsvReader`, `JWTDecodedListener`, `NotificationService`, `SyncDatabaseConnection`, `UserAccessValidation`) |
| Security | 1 | `src/Security/UserProvider.php` |
| Console commands | 0 | `src/Command/` is empty |

Stack: PHP ≥ 8.2, Symfony 7.0, `doctrine/orm ^3.1`, `doctrine/dbal ^3`,
`lexik/jwt-authentication-bundle ^3.0`, `knplabs/knp-paginator-bundle ^6.4`,
`nelmio/cors-bundle`. Mapping driver = **PHP attributes** only (no XML/YAML mapping).

### 1.2 Doctrine configuration (`config/packages/doctrine.yaml`)

```yaml
doctrine:
  dbal:
    url: '%env(resolve:DATABASE_URL)%'      # ONE connection, no multi-DB, no read replica
    use_savepoints: true
  orm:
    naming_strategy: doctrine.orm.naming_strategy.underscore_number_aware
    auto_mapping: true
    report_fields_where_declared: true
    enable_lazy_ghost_objects: true
    mappings:
      App: { type: attribute, dir: src/Entity, prefix: App\Entity, alias: App }
    metadata_cache_driver / query_cache_driver / result_cache_driver: APCu pools
    second_level_cache: { enabled: true, region_cache_driver: APCu pool }
```

Key facts for the port:

* **Single DBAL connection** driven exclusively by the `DATABASE_URL` env var.
  There is *no* second entity manager. (A *runtime, non-Doctrine* second
  connection does exist — `src/Service/SyncDatabaseConnection.php` — built from
  the `SyncConnection` entity rows for biometric/worker sync. See §3h.)
* **Second-level cache is enabled globally** but **no entity declares
  `#[ORM\Cache]`**, so nothing is actually second-level cached. Dead config.
* **APCu** is used for metadata/query/result caches in *all* environments
  including `test`.
* MySQL/MariaDB is the target platform — every migration emits MySQL DDL
  (`TINYINT(1)`, `ALTER TABLE … CHANGE`, `DROP FOREIGN KEY FK_…`).

### 1.3 Table-name derivation — the exact rule

**There is not a single `#[ORM\Table]` attribute anywhere in `src/Entity`.**
Verified: `grep -rn "ORM\\Table|ORM\\Index|ORM\\UniqueConstraint" src/Entity` returns
only one *commented-out* line in `User.php`
(`// #[ORM\UniqueConstraint(name: 'UNIQ_IDENTIFIER_EMAIL', fields: ['email'])]`).

Therefore **every** table name is machine-derived by
`Doctrine\ORM\Mapping\UnderscoreNamingStrategy` (CASE_LOWER, number-aware) from the
**class short name** (namespace stripped). The relevant vendor code is:

```php
// vendor/doctrine/orm/src/Mapping/UnderscoreNamingStrategy.php
public function classToTableName(string $className): string {
    if (str_contains($className, '\\')) {
        $className = substr($className, strrpos($className, '\\') + 1);
    }
    return $this->underscore($className);
}

private function underscore(string $string): string {
    $string = preg_replace('/(?<=[a-z0-9])([A-Z])/', '_$1', $string);
    return strtolower($string);   // CASE_LOWER
}
```

#### The rule, stated precisely

> Insert `_` **only** before an uppercase letter that is immediately preceded by a
> **lowercase letter or a digit**, then lowercase the whole string.
> Names are **not** pluralised or singularised — the table name is exactly whatever
> the class was called (so plural class names ⇒ plural tables, singular ⇒ singular;
> the codebase is inconsistent, see §7).

Two consequences that matter enormously for the port:

1. **`(?<=[a-z0-9])` means digits keep the following capital glued** — this is what
   "number aware" means in doctrine-bundle's service id. `Foo2Bar` → `foo2_bar`
   (a digit *does* trigger a split), whereas the *non*-number-aware strategy
   (`/(?<=[a-z])([A-Z])/`) would yield `foo2bar`. **No entity in this codebase
   contains a digit**, so the two strategies produce identical output here — the
   choice is cosmetic for this schema.
2. **Runs of consecutive capitals are NOT split.** An acronym prefix such as
   `SSS`, `DTR` or `PhilHealth`'s `H` only splits where a lowercase/digit precedes
   the capital.

#### Worked examples (all machine-verified against the regex)

| Class short name | Split points (lowercase/digit → Upper) | Derived table |
|---|---|---|
| `EmployeeRecords` | `e`→`R` | `employee_records` |
| `PagibigLoansHistory` | `a`→`L`, `s`→`H` | `pagibig_loans_history` |
| `EmployeePayrollProfile` | `e`→`P`, `l`→`P` | `employee_payroll_profile` |
| `PhilHealthConfig` | `l`→`H`, `h`→`C` | `phil_health_config` |
| `DTRAdjutments` | *(none — `D`,`T`,`R`,`A` are all preceded by uppercase)* | **`dtradjutments`** |
| `SSSConfig` | *(none)* | **`sssconfig`** |
| `SSSLoans` | *(none)* | **`sssloans`** |
| `SSSLoansHistory` | `s`→`H` only | **`sssloans_history`** |
| `EmpTask` | `p`→`T` | `emp_task` |
| `SubModules` | `b`→`M` | `sub_modules` |
| `MainModules` | `n`→`M` | `main_modules` |
| `ThirteenthMonthPayConfig` | `h`→`M`, `h`→`P`, `y`→`C` | `thirteenth_month_pay_config` |
| `User` | none | `user` (a **reserved word** in MySQL 8 — must be back-ticked) |

> ⚠️ **CORRECTION TO THE BRIEF.** The task statement asserted
> `DTRAdjutments → d_t_r_adjutments` and `SSSConfig → s_s_s_config`.
> **That is wrong for this codebase.** Doctrine's `UnderscoreNamingStrategy` never
> splits a capital that follows another capital. Empirical proof from the repo's own
> migration `Version20250303071748.php`:
> `ALTER TABLE sssconfig ADD is_archived TINYINT(1) DEFAULT NULL;`
> — the real, deployed table is **`sssconfig`**, not `s_s_s_config`.
> By the same rule the real tables are **`dtradjutments`**, **`sssloans`**,
> **`sssloans_history`**. Port these literal names or the migration will not match
> production data.

The same `underscore()` function also derives:

* **column names** from property names — but in this codebase almost every scalar
  property is *already* written in `snake_case`, so `property == column` for the vast
  majority. The exceptions (camelCase properties that therefore get split) are
  catalogued per-entity in §3 and summarised in §7.6.
* **join columns**: `underscore(propertyName) + '_id'`, e.g. property
  `$emp_record` → column `emp_record_id`; property `$payroll_profile` →
  `payroll_profile_id`; property `$affiliated_company` → `affiliated_company_id`.
* **join tables** for `ManyToMany`: `table(source) + '_' + table(target)`, and
  join-key columns `table(entity) + '_id'`. Only one ManyToMany exists
  (`YearlyEmployeeLeave.selected_leave_policies` ⇄ `LeavePolicy`), giving join table
  **`yearly_employee_leave_leave_policy`** with columns
  `yearly_employee_leave_id`, `leave_policy_id`.

### 1.4 Lifecycle callbacks / listeners

* **Zero** `#[ORM\HasLifecycleCallbacks]`, `#[ORM\PrePersist]`, `#[ORM\PreUpdate]`,
  `#[ORM\PostLoad]`, … in `src/Entity`. Verified by grep.
* There are **no Doctrine event subscribers/listeners** registered anywhere.
* Consequence: **there is no automatic `created_at` / `updated_at` population.**
  The handful of timestamp columns that exist (`LeaveRequest.created_at`,
  `LoanHistory.createdAt`, `WorkerLogs.created_at`, `AuditTrailLog.datetime`,
  `EmployeePayroll.date_generated`) are set **manually in controller code**.
  A SQLAlchemy port must replicate this explicitly (or, better, add
  `server_default=func.now()` — but be aware behaviour then *changes*).
* Only one behavioural interceptor exists and it is a *Symfony kernel* listener,
  not a Doctrine one: `src/Service/JWTDecodedListener.php`.

### 1.5 Identifier convention

Every single entity uses the identical PK definition:

```php
#[ORM\Id]
#[ORM\GeneratedValue]
#[ORM\Column]
private ?int $id = null;
```

⇒ `id INT AUTO_INCREMENT NOT NULL PRIMARY KEY` on all 58 tables.
There are **no composite keys, no natural keys, no UUIDs, no sequences**.
SQLAlchemy equivalent: `Column(Integer, primary_key=True, autoincrement=True)`.

### 1.6 Doctrine → MySQL → SQLAlchemy type crib sheet

| Doctrine mapping in this repo | MySQL DDL | SQLAlchemy |
|---|---|---|
| `#[ORM\Column]` on `?int` | `INT NOT NULL` | `Integer` |
| `#[ORM\Column(type: Types::SMALLINT)]` | `SMALLINT NOT NULL` | `SmallInteger` |
| `#[ORM\Column]` on `?float` | `DOUBLE PRECISION NOT NULL` | `Float` (⚠️ see §7.9) |
| `#[ORM\Column]` on `?bool` | `TINYINT(1) NOT NULL` | `Boolean` |
| `#[ORM\Column(length: N)]` on `?string` | `VARCHAR(N) NOT NULL` | `String(N)` |
| `#[ORM\Column]` on `?string` (no length) | `VARCHAR(255) NOT NULL` | `String(255)` |
| `#[ORM\Column(type: Types::TEXT)]` | `LONGTEXT` | `Text` |
| `#[ORM\Column(type: Types::DATE_MUTABLE)]` | `DATE` | `Date` |
| `#[ORM\Column(type: Types::DATETIME_MUTABLE)]` | `DATETIME` | `DateTime` |
| `#[ORM\Column]` on `?\DateTimeImmutable` | `DATETIME` (comment `(DC2Type:datetime_immutable)`) | `DateTime` |
| `#[ORM\Column(type: Types::TIME_MUTABLE)]` | `TIME` | `Time` |
| `#[ORM\Column]` on `array $roles` / `?array` | `JSON` | `JSON` |
| `#[ORM\Column(type: Types::ARRAY)]` | `LONGTEXT` + `(DC2Type:array)` — **PHP `serialize()` blob** | ⚠️ see §7.4 |
| `nullable: true` added | ` DEFAULT NULL` | `nullable=True` |

**Critical:** `Types::ARRAY` is *not* JSON. Doctrine stores a PHP `serialize()`
string in a `LONGTEXT` column. Any non-PHP consumer (SQLAlchemy) cannot read these
columns without a PHP-unserialize shim or a data migration. All 25 `SubModules`
columns, all 5 `MainModules` columns and `Shifts.days_of_week` are affected — i.e.
**the entire RBAC permission store is PHP-serialised text**. See §7.4.

---

## 2. Migration history

Only **4** migrations exist in `migrations/`. **None of them creates a table.**
All four are `ALTER TABLE` deltas produced by `make:migration` late in the project's
life. The entire initial schema (58 tables) was therefore created **outside the
migration system** — almost certainly via `doctrine:schema:update --force` or a
hand-restored dump. `migrations/.gitignore` is an empty file.

> **Porting implication:** you cannot reconstruct the production schema by replaying
> these migrations. The *entity attributes* (§3) are the only complete description,
> and they must be reconciled with whatever is actually in the live MySQL database.

### 2.1 `Version20250213092844` — 2025-02-13 09:28:44

`getDescription()` returns `''` (all four do).

**up()**
```sql
ALTER TABLE division DROP FOREIGN KEY FK_10174714899FB366;
ALTER TABLE division ADD CONSTRAINT FK_10174714899FB366
      FOREIGN KEY (director_id) REFERENCES employee_records (id);
ALTER TABLE leave_policy
  CHANGE name   name   VARCHAR(255) DEFAULT NULL,
  CHANGE year   year   VARCHAR(255) DEFAULT NULL,
  CHANGE gender gender VARCHAR(255) DEFAULT NULL;
```
**What it did**
1. **Re-pointed `division.director_id`** from `user(id)` to `employee_records(id)`.
   This is the DB half of changing `Division::$director` from `?User` to
   `?EmployeeRecords`. The FK name `FK_10174714899FB366` is Doctrine's auto hash and
   is *preserved* across the change.
2. **Relaxed `leave_policy.name`, `.year`, `.gender` to nullable** (previously
   `NOT NULL`). Matches `#[ORM\Column(length: 255, nullable: true)]` on those three
   `LeavePolicy` properties today.

**down()** reverses both (re-points `director_id` at `user(id)`, restores NOT NULL).

### 2.2 `Version20250220051513` — 2025-02-20 05:15:13

**up()**
```sql
ALTER TABLE division DROP FOREIGN KEY FK_10174714899FB366;
ALTER TABLE division ADD CONSTRAINT FK_10174714899FB366
      FOREIGN KEY (director_id) REFERENCES employee_records (id);
ALTER TABLE holiday_config  ADD archived TINYINT(1) DEFAULT NULL;
ALTER TABLE leave_policy
  CHANGE name name VARCHAR(255) DEFAULT NULL,
  CHANGE year year VARCHAR(255) DEFAULT NULL,
  CHANGE gender gender VARCHAR(255) DEFAULT NULL;
ALTER TABLE yearly_holiday ADD archived TINYINT(1) DEFAULT NULL;
```
**What it did**
1. Added the soft-delete flags **`holiday_config.archived`** and
   **`yearly_holiday.archived`** (`TINYINT(1) NULL`).
2. **Re-emitted the identical `division` FK swap and the identical `leave_policy`
   nullability change from 2.1.** This is *idempotent noise* — the developer ran
   `make:migration` without having executed the previous one, so the diff was
   regenerated. Running 2.1 then 2.2 works (the statements are re-runnable), but it
   proves migration state and DB state were already out of sync in Feb 2025.

**down()** drops the two `archived` columns and reverses the other two changes.

### 2.3 `Version20250303071748` — 2025-03-03 07:17:48

**up()**
```sql
ALTER TABLE sssconfig ADD is_archived TINYINT(1) DEFAULT NULL;
```
Added the soft-delete flag for `SSSConfig::$isArchived`.

**This migration is the empirical proof of the table-naming rule in §1.3**: the table
is literally `sssconfig`, and the column is `is_archived` (from camelCase property
`$isArchived` → `underscore()` → `is_archived`).

**down()**: `ALTER TABLE sssconfig DROP is_archived;`

### 2.4 `Version20250506061501` — 2025-05-06 06:15:01 (latest)

**up()**
```sql
ALTER TABLE employee_records CHANGE date_hired date_hired DATETIME DEFAULT NULL;
```
Made `employee_records.date_hired` nullable (was `DATETIME NOT NULL`), matching
`#[ORM\Column(type: Types::DATETIME_MUTABLE, nullable: true)]`.

**down()**: restores `DATETIME NOT NULL`.

### 2.5 Entity ↔ migration DRIFT

Everything below exists in the **entity attributes** but has **no migration**. Each
item was applied to the live DB by `schema:update` (or is silently missing from it).
This is the complete drift list — every entity/column/table not accounted for by the
four migrations above:

| Drift | Detail |
|---|---|
| **All 58 `CREATE TABLE`s** | No migration creates any table. `employee_records`, `user`, `employee_payroll`, `sssconfig`, `dtradjutments`, … all originate outside migrations. |
| `PayrollGroups` (`payroll_groups`) | Entity + `EmployeePayroll.payroll_group_id` FK. No migration. |
| `PagibigLoans`, `PagibigLoansHistory`, `SSSLoans`, `SSSLoansHistory`, `CashAdvance`, `CashAdvanceHistory` | Whole loan/CA subsystem — no migrations at all. |
| `SalaryAdjustment`, `TaxShield`, `ThirteenthMonthPayConfig`, `PayrollCalculationConfig` | No migrations. |
| `EmployeeOvertimeRequest`, `DTRAdjutments`, `AccountabilityRecords`, `Notifications`, `AuditTrailLog`, `SyncConnection`, `ContractTypes`, `AttendanceTypes`, `Options`, `ProjectType`, `AffiliatedCompany` | No migrations. |
| `SelectedEmployeeLeaves`, `YearlyEmployeeLeave`, `LeaveRequest` | No migrations. |
| `MainModules`, `SubModules` (25 `array` cols), `UserType`, `Shifts` | No migrations — the entire RBAC store is untracked. |
| `EmployeePayroll.total_tax_shield`, `.sss_calamity_loan`, `.sss_loan`, `.hdmf_loan`, `.hdmf_calamity_loan`, `.hdmf_mp2`, `.total_ca` | Late-added nullable float columns; no migration. |
| `EmployeePayrollProfile.daily_rate_non_tax`, `.allowance_non_tax`, `.include_salary_adjustment_for_thirteenth_month`, `.include_salary_for_thirteenth_month`, `.include_taxshield__for_thirteenth_month` | No migration. Note the **double underscore typo** in the last one → column `include_taxshield__for_thirteenth_month`. |
| `EmployeeRecords.profile_photo_path`, `.probationary_date`, `.regularization_date`, `.telephone`, `.cellphone`, `.archived` | No migration. |
| `User.reset_token` (VARCHAR 1000), `.token_expiry`, `.is_worker`, `.is_active`, `.is_straight_time`, `.is_assignable_proj`, `.emp_shift_id`, `.archived`, `.username` | No migration. |
| `Shifts.days_of_week` (`Types::ARRAY`), `.lunch_break_duration`, `.total_hours_minus_lunch` | No migration. |
| `WorkerLogs.created_at`, `.is_time_calculated`, `.rendered_hours`, `.undertime`, `.overtime_approved`, `.attendance_status_id` | No migration. |
| **Soft-delete columns added ad-hoc** | `archived` on Project/Subdivision/Phase/Category/Owner/EmpTask/EmployeeProjects/ModelTypes/Shifts/EmployeeRecords/User; `isArchived` on Division/Department/SSSConfig; `is_archived` only on `sssconfig`. Only 3 of these ever got a migration. |
| **Two structurally broken mappings** (see §7.2) | `EmployeeRecords.accountabilityRecords` → `mappedBy: 'emp_id'` (property is `employee_record`); `LeavePolicy.yearlyEmployeeLeaves` → `mappedBy: 'selected_leave_policies'` (property does not exist on `YearlyEmployeeLeave` at all). The implied join table `yearly_employee_leave_leave_policy` therefore may or may not exist in the DB. |

---

## 3. Per-domain entity reference

**Global facts that apply to EVERY table below (stated once, not repeated per row):**

* PK is always `id INT AUTO_INCREMENT NOT NULL`.
* **No column anywhere declares `unique: true`** → the `Uniq` column is always `No`.
  The only unique indexes MySQL will have are the primary keys (plus the implicit
  `UNIQ_*` that Doctrine creates for the *owning* side of a `OneToOne`).
* **No column anywhere declares `options: ['default' => …]`** → the `Default` column
  is always `—`. `nullable: true` yields `DEFAULT NULL`; everything else is
  `NOT NULL` with no default.
* **No `#[ORM\JoinColumn(onDelete: …)]` anywhere** → every FK is MySQL's default
  `RESTRICT`/`NO ACTION`. The `onDelete` column below is therefore always `—`.
* **No `orphanRemoval: true` anywhere** → always `false`.
* **No `#[ORM\Index]` / `#[ORM\UniqueConstraint]` anywhere** → the only indexes are
  the PKs and the FK indexes Doctrine auto-creates for join columns.
* `cascade` is only ever `['persist','remove']`, never `['all']`, never `detach`/`merge`.
* Join-column naming is always `underscore(propertyName) + '_id'`.

Legend: *Side* = owning (holds the FK) or inverse (mapped).

### 3a. Employee & HR core

#### `EmployeeRecords` → **`employee_records`**

Central HR master record. 31 scalar columns + 16 associations. **Soft-deleted** via nullable `archived`. `employee_code` is the business key used everywhere but is **NOT unique-constrained** and **NOT indexed**.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `first_name` | `first_name` | `string` | 255 | No | No | — | VARCHAR(255) |
| `middle_name` | `middle_name` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `last_name` | `last_name` | `string` | 255 | No | No | — | VARCHAR(255) |
| `extension` | `extension` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `employee_code` | `employee_code` | `string` | 255 | No | No | — | VARCHAR(255). Business key. No UNIQUE, no index. Looked up by `EmployeeRecordsRepository::findByCode()` |
| `birthdate` | `birthdate` | `datetime` | — | No | No | — | DATETIME. DATETIME although only the date is meaningful |
| `birth_place` | `birth_place` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `age` | `age` | `smallint` | — | No | No | — | SMALLINT. **Denormalised** — derived from `birthdate`, never recomputed |
| `gender` | `gender` | `string` | 255 | No | No | — | VARCHAR(255). Implicit enum, see §4 |
| `civil_status` | `civil_status` | `string` | 255 | No | No | — | VARCHAR(255). Implicit enum, see §4 |
| `email` | `email` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `zip_code` | `zip_code` | `smallint` | — | Yes | No | — | SMALLINT. SMALLINT — cannot hold a leading-zero PH ZIP; overflows above 32767 |
| `area` | `area` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `present_barangay` | `present_barangay` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `present_city` | `present_city` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `same_address` | `same_address` | `boolean` | — | Yes | No | — | TINYINT(1). If true, `permanent_*` should mirror `present_*` — enforced only in JS |
| `permanent_barangay` | `permanent_barangay` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `permanent_city` | `permanent_city` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `date_hired` | `date_hired` | `datetime` | — | Yes | No | — | DATETIME. Made nullable by migration 2.4 |
| `employee_status` | `employee_status` | `string` | 255 | No | No | — | VARCHAR(255). Implicit enum, see §4. Queried as a literal `'Active'` in 9 places |
| `position` | `position` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `employment_type` | `employment_type` | `string` | 255 | Yes | No | — | VARCHAR(255). Free text. **Not** an FK to `contract_types` |
| `contract_expiry_date` | `contract_expiry_date` | `datetime` | — | Yes | No | — | DATETIME |
| `date_separated` | `date_separated` | `datetime` | — | Yes | No | — | DATETIME |
| `probationary_date` | `probationary_date` | `datetime` | — | Yes | No | — | DATETIME |
| `regularization_date` | `regularization_date` | `datetime` | — | Yes | No | — | DATETIME |
| `archived` | `archived` | `boolean` | — | Yes | No | — | TINYINT(1). Soft delete. `NULL` == not archived (all repo predicates are `archived IS NULL OR archived = false`) |
| `telephone` | `telephone` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `cellphone` | `cellphone` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `profile_photo_path` | `profile_photo_path` | `string` | 255 | Yes | No | — | VARCHAR(255). Filesystem path, not a blob |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `division` | ManyToOne | Division | owning | `division_id` | NULL (implicit) | — | — | false | inversedBy `employeeRecords` |
| `department` | ManyToOne | Department | owning | `department_id` | NULL (implicit) | — | — | false | inversedBy `employeeRecords` |
| `user` | OneToOne | User | owning | `user_id` | NULL (implicit) | — | persist, remove | false | inversedBy `employeeRecords` |
| `workers` | OneToMany | Worker | inverse | — | — | — | — | false | mappedBy `emp_record` |
| `employeeProjects` | OneToMany | EmployeeProjects | inverse | — | — | — | — | false | mappedBy `employee` |
| `employeeAdditionalRecords` | OneToOne | EmployeeAdditionalRecords | inverse | — | — | — | persist, remove | false | mappedBy `employee_code` |
| `employeeAttachments` | OneToMany | EmployeeAttachments | inverse | — | — | — | — | false | mappedBy `employee` |
| `loanHistories` | OneToMany | LoanHistory | inverse | — | — | — | — | false | mappedBy `employee_record` |
| `affiliated_company` | ManyToOne | AffiliatedCompany | owning | `affiliated_company_id` | NULL (implicit) | — | — | false | inversedBy `employeeRecords` |
| `leaveRequests` | OneToMany | LeaveRequest | inverse | — | — | — | — | false | mappedBy `emp_record` |
| `yearlyEmployeeLeaves` | OneToMany | YearlyEmployeeLeave | inverse | — | — | — | — | false | mappedBy `emp_record` |
| `accountabilityRecords` | OneToMany | AccountabilityRecords | inverse | — | — | — | — | false | mappedBy `emp_id` |
| `employeeOvertimeRequests` | OneToMany | EmployeeOvertimeRequest | inverse | — | — | — | — | false | mappedBy `emp_id` |
| `dTRAdjutments` | OneToMany | DTRAdjutments | inverse | — | — | — | — | false | mappedBy `emp_record` |
| `notifications` | OneToMany | Notifications | inverse | — | — | — | — | false | mappedBy `recipient_employee_record` |
| `sender_notifications` | OneToMany | Notifications | inverse | — | — | — | — | false | mappedBy `sender_employee_record` |

#### `EmployeeAdditionalRecords` → **`employee_additional_records`**

Employee 201-file extension. **11 of its 21 columns are `json`** — the entire employment history, education, dependents, violations, etc. are unnormalised JSON documents.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `employment_history` | `employment_history` | `json` | — | Yes | No | — | JSON |
| `past_employment_record` | `past_employment_record` | `json` | — | Yes | No | — | JSON |
| `educational_background` | `educational_background` | `json` | — | Yes | No | — | JSON |
| `seminars_trainings` | `seminars_trainings` | `json` | — | Yes | No | — | JSON |
| `assessments_exams` | `assessments_exams` | `json` | — | Yes | No | — | JSON |
| `skills` | `skills` | `json` | — | Yes | No | — | JSON |
| `awards` | `awards` | `json` | — | Yes | No | — | JSON |
| `licenses` | `licenses` | `json` | — | Yes | No | — | JSON |
| `dependents` | `dependents` | `json` | — | Yes | No | — | JSON |
| `violations` | `violations` | `json` | — | Yes | No | — | JSON |
| `medical_drug_tests` | `medical_drug_tests` | `json` | — | Yes | No | — | JSON |
| `school_graduated` | `school_graduated` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `course` | `course` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `career_band_level` | `career_band_level` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `career_global_grade` | `career_global_grade` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `cash_card_number` | `cash_card_number` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `hmo_account` | `hmo_account` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `sss_number` | `sss_number` | `string` | 255 | Yes | No | — | VARCHAR(255). Government ID stored as free text, no format validation, not unique |
| `philhealth_number` | `philhealth_number` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `pagibig_number` | `pagibig_number` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `tin_number` | `tin_number` | `string` | 255 | Yes | No | — | VARCHAR(255). Government ID stored as free text, no format validation, not unique |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `employee_code` | OneToOne | EmployeeRecords | owning | `employee_code_id` | NULL (implicit) | — | persist, remove | false | inversedBy `employeeAdditionalRecords` |

#### `EmployeeAttachments` → **`employee_attachments`**

Uploaded 201-file documents. Files live on disk; only paths are stored.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `type` | `type` | `string` | 255 | Yes | No | — | VARCHAR(255). Free-text document category (no lookup table) |
| `attachment_name` | `attachment_name` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `attachment_size` | `attachment_size` | `string` | 255 | Yes | No | — | VARCHAR(255). Size stored as **VARCHAR**, not an integer |
| `date_uploaded` | `date_uploaded` | `datetime` | — | Yes | No | — | DATETIME |
| `file` | `file` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `original_file_name` | `original_file_name` | `string` | 255 | Yes | No | — | VARCHAR(255) |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `employee` | ManyToOne | EmployeeRecords | owning | `employee_id` | NULL (implicit) | — | — | false | inversedBy `employeeAttachments` |

#### `AccountabilityRecords` → **`accountability_records`**

Company property issued to an employee (laptop, tools…).

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `item_name` | `item_name` | `string` | 255 | No | No | — | VARCHAR(255) |
| `item_count` | `item_count` | `float` | — | No | No | — | DOUBLE PRECISION. `float` for a **count of items** — should be integer |
| `status` | `status` | `integer` | — | No | No | — | INT. Implicit enum 0/1/2, see §4 |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `employee_record` | ManyToOne | EmployeeRecords | owning | `employee_record_id` | NULL (implicit) | — | — | false | inversedBy `accountabilityRecords` |

#### `AffiliatedCompany` → **`affiliated_company`**

Tiny lookup: the group company an employee is payrolled under.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `code` | `code` | `string` | 255 | No | No | — | VARCHAR(255) |
| `name` | `name` | `string` | 255 | No | No | — | VARCHAR(255) |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `employeeRecords` | OneToMany | EmployeeRecords | inverse | — | — | — | — | false | mappedBy `affiliated_company` |

#### `Division` → **`division`**

Org unit level 1. Soft delete via `isArchived` (camelCase → column `is_archived`).

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `code` | `code` | `string` | 255 | No | No | — | VARCHAR(255) |
| `name` | `name` | `string` | 255 | No | No | — | VARCHAR(255) |
| `description` | `description` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `isArchived` | `is_archived` | `boolean` | — | Yes | No | — | TINYINT(1) |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `director` | ManyToOne | EmployeeRecords | owning | `director_id` | NULL (implicit) | — | — | false | **unidirectional** |
| `employeeRecords` | OneToMany | EmployeeRecords | inverse | — | — | — | — | false | mappedBy `division` |
| `departments` | OneToMany | Department | inverse | — | — | — | — | false | mappedBy `division` |
| `notifications` | OneToMany | Notifications | inverse | — | — | — | — | false | mappedBy `recipient_division` |

#### `Department` → **`department`**

Org unit level 2, child of Division. Soft delete via `isArchived`.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `code` | `code` | `string` | 255 | No | No | — | VARCHAR(255) |
| `name` | `name` | `string` | 255 | No | No | — | VARCHAR(255) |
| `description` | `description` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `isArchived` | `is_archived` | `boolean` | — | Yes | No | — | TINYINT(1) |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `manager` | ManyToOne | User | owning | `manager_id` | NULL (implicit) | — | — | false | **unidirectional** |
| `employeeRecords` | OneToMany | EmployeeRecords | inverse | — | — | — | — | false | mappedBy `department` |
| `division` | ManyToOne | Division | owning | `division_id` | NULL (implicit) | — | — | false | inversedBy `departments` |
| `leavePolicies` | OneToMany | LeavePolicy | inverse | — | — | — | — | false | mappedBy `department` |
| `recipient_division` | OneToMany | Notifications | inverse | — | — | — | — | false | mappedBy `recipient_department` |

#### `ContractTypes` → **`contract_types`**

Lookup table with a full CRUD API and **zero consumers** — nothing references it (see §6).

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `name` | `name` | `string` | 255 | No | No | — | VARCHAR(255) |
| `code` | `code` | `string` | 255 | No | No | — | VARCHAR(255) |
| `archived` | `archived` | `boolean` | — | No | No | — | TINYINT(1). **NOT NULL** boolean here, unlike every other `archived` column in the schema |

### 3b. Payroll

#### `EmployeePayrollProfile` → **`employee_payroll_profile`**

Per-employee payroll master. 26 monetary/rate columns, **all `float`**. Holds *current* loan balances denormalised alongside the `*Loans` tables.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `monthly_salary` | `monthly_salary` | `float` | — | No | No | — | DOUBLE PRECISION |
| `allowance` | `allowance` | `float` | — | No | No | — | DOUBLE PRECISION |
| `overtime_rate` | `overtime_rate` | `float` | — | No | No | — | DOUBLE PRECISION |
| `late_rate` | `late_rate` | `float` | — | No | No | — | DOUBLE PRECISION |
| `sss_loan` | `sss_loan` | `float` | — | No | No | — | DOUBLE PRECISION. Denormalised running balance; also modelled properly in `sssloans` / `sssloans_history` |
| `sss_loan_deduction` | `sss_loan_deduction` | `float` | — | No | No | — | DOUBLE PRECISION |
| `hdmf_loan` | `hdmf_loan` | `float` | — | No | No | — | DOUBLE PRECISION. Denormalised running balance; also in `pagibig_loans` / `pagibig_loans_history` |
| `hdmf_loan_deduction` | `hdmf_loan_deduction` | `float` | — | No | No | — | DOUBLE PRECISION |
| `cash_advance` | `cash_advance` | `float` | — | No | No | — | DOUBLE PRECISION. Denormalised running balance; also in `cash_advance` / `cash_advance_history` |
| `cash_advance_deduction` | `cash_advance_deduction` | `float` | — | No | No | — | DOUBLE PRECISION |
| `other_loans` | `other_loans` | `float` | — | No | No | — | DOUBLE PRECISION |
| `other_loans_deduction` | `other_loans_deduction` | `float` | — | No | No | — | DOUBLE PRECISION |
| `employer_sss_contribution` | `employer_sss_contribution` | `float` | — | No | No | — | DOUBLE PRECISION |
| `employer_pagibig_contribution` | `employer_pagibig_contribution` | `float` | — | No | No | — | DOUBLE PRECISION |
| `employer_philhealth_contribution` | `employer_philhealth_contribution` | `float` | — | No | No | — | DOUBLE PRECISION |
| `accident_insurance` | `accident_insurance` | `float` | — | No | No | — | DOUBLE PRECISION |
| `thirteenth_month_pay` | `thirteenth_month_pay` | `float` | — | No | No | — | DOUBLE PRECISION |
| `daily_rate` | `daily_rate` | `float` | — | No | No | — | DOUBLE PRECISION |
| `hourly_rate` | `hourly_rate` | `float` | — | No | No | — | DOUBLE PRECISION |
| `daily_rate_non_tax` | `daily_rate_non_tax` | `float` | — | No | No | — | DOUBLE PRECISION |
| `allowance_non_tax` | `allowance_non_tax` | `float` | — | No | No | — | DOUBLE PRECISION |
| `include_salary_adjustment_for_thirteenth_month` | `include_salary_adjustment_for_thirteenth_month` | `boolean` | — | No | No | — | TINYINT(1) |
| `include_salary_for_thirteenth_month` | `include_salary_for_thirteenth_month` | `boolean` | — | No | No | — | TINYINT(1) |
| `include_taxshield__for_thirteenth_month` | `include_taxshield__for_thirteenth_month` | `boolean` | — | No | No | — | TINYINT(1). **Double-underscore typo** — real column is `include_taxshield__for_thirteenth_month` |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `sss_contribution` | ManyToOne | SSSConfig | owning | `sss_contribution_id` | NULL (implicit) | — | — | false | inversedBy `employeePayrollProfiles` |
| `tax_contribution` | ManyToOne | TaxConfig | owning | `tax_contribution_id` | NULL (implicit) | — | — | false | inversedBy `employeePayrollProfiles` |
| `pagibig_contribution` | ManyToOne | PagibigConfig | owning | `pagibig_contribution_id` | NULL (implicit) | — | — | false | inversedBy `employeePayrollProfiles` |
| `philhealth_contribution` | ManyToOne | PhilHealthConfig | owning | `philhealth_contribution_id` | NULL (implicit) | — | — | false | inversedBy `employeePayrollProfiles` |
| `employeePayrolls` | OneToMany | EmployeePayroll | inverse | — | — | — | — | false | mappedBy `payroll_profile` |
| `employee_record` | OneToOne | EmployeeRecords | inverse | — | — | — | persist, remove | false | **unidirectional** |
| `cashAdvances` | OneToMany | CashAdvance | inverse | — | — | — | — | false | mappedBy `payroll_profile` |
| `pagibigLoans` | OneToMany | PagibigLoans | inverse | — | — | — | — | false | mappedBy `payroll_profile` |
| `sss_loans` | OneToMany | SSSLoans | inverse | — | — | — | — | false | mappedBy `payroll_profile` |
| `sSSLoansHistories` | OneToMany | SSSLoansHistory | inverse | — | — | — | — | false | mappedBy `payroll_profile` |
| `pagibigLoansHistories` | OneToMany | PagibigLoansHistory | inverse | — | — | — | — | false | mappedBy `payroll_profile` |
| `cashAdvanceHistories` | OneToMany | CashAdvanceHistory | inverse | — | — | — | — | false | mappedBy `payroll_profile` |
| `thirteenthMonthPayConfig` | OneToOne | ThirteenthMonthPayConfig | inverse | — | — | — | persist, remove | false | mappedBy `employee_payroll_profile` |

#### `EmployeePayroll` → **`employee_payroll`**

One generated payslip per employee per cut-off. 24 monetary columns, all `float`.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `basic_salary` | `basic_salary` | `float` | — | No | No | — | DOUBLE PRECISION |
| `overtime_salary` | `overtime_salary` | `float` | — | No | No | — | DOUBLE PRECISION |
| `total_salary` | `total_salary` | `float` | — | No | No | — | DOUBLE PRECISION |
| `total_deduction` | `total_deduction` | `float` | — | No | No | — | DOUBLE PRECISION |
| `net_salary` | `net_salary` | `float` | — | No | No | — | DOUBLE PRECISION |
| `thirteenth_month_pay` | `thirteenth_month_pay` | `float` | — | No | No | — | DOUBLE PRECISION |
| `sss_share` | `sss_share` | `float` | — | No | No | — | DOUBLE PRECISION |
| `philhealth_share` | `philhealth_share` | `float` | — | No | No | — | DOUBLE PRECISION |
| `hdmf_contribution` | `hdmf_contribution` | `float` | — | No | No | — | DOUBLE PRECISION |
| `insurance_contribution` | `insurance_contribution` | `float` | — | No | No | — | DOUBLE PRECISION |
| `tax_contribution` | `tax_contribution` | `float` | — | No | No | — | DOUBLE PRECISION |
| `cash_advance_deduction` | `cash_advance_deduction` | `float` | — | No | No | — | DOUBLE PRECISION |
| `undertime_deduction` | `undertime_deduction` | `float` | — | No | No | — | DOUBLE PRECISION |
| `rendered_days` | `rendered_days` | `float` | — | No | No | — | DOUBLE PRECISION. float days |
| `date_generated` | `date_generated` | `datetime` | — | No | No | — | DATETIME. Set manually in the controller (no lifecycle callback) |
| `total_tax_shield` | `total_tax_shield` | `float` | — | Yes | No | — | DOUBLE PRECISION |
| `date_start` | `date_start` | `date` | — | No | No | — | DATE |
| `date_end` | `date_end` | `date` | — | No | No | — | DATE |
| `sss_calamity_loan` | `sss_calamity_loan` | `float` | — | Yes | No | — | DOUBLE PRECISION |
| `sss_loan` | `sss_loan` | `float` | — | Yes | No | — | DOUBLE PRECISION |
| `hdmf_loan` | `hdmf_loan` | `float` | — | Yes | No | — | DOUBLE PRECISION |
| `hdmf_calamity_loan` | `hdmf_calamity_loan` | `float` | — | Yes | No | — | DOUBLE PRECISION |
| `hdmf_mp2` | `hdmf_mp2` | `float` | — | Yes | No | — | DOUBLE PRECISION |
| `total_ca` | `total_ca` | `float` | — | Yes | No | — | DOUBLE PRECISION |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `payroll_profile` | ManyToOne | EmployeePayrollProfile | owning | `payroll_profile_id` | NULL (implicit) | — | — | false | inversedBy `employeePayrolls` |
| `taxShield` | OneToOne | TaxShield | inverse | — | — | — | persist, remove | false | mappedBy `payroll` |
| `cashAdvanceHistories` | OneToMany | CashAdvanceHistory | inverse | — | — | — | — | false | mappedBy `payroll` |
| `salaryAdjustment` | OneToOne | SalaryAdjustment | inverse | — | — | — | persist, remove | false | mappedBy `payroll` |
| `payroll_group` | ManyToOne | PayrollGroups | owning | `payroll_group_id` | NULL (implicit) | — | — | false | inversedBy `employeePayrolls` |

#### `PayrollGroups` → **`payroll_groups`**

Payroll cut-off period header (date_start/date_end/remarks). No status column.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `date_start` | `date_start` | `date` | — | No | No | — | DATE |
| `date_end` | `date_end` | `date` | — | No | No | — | DATE |
| `remarks` | `remarks` | `string` | 255 | Yes | No | — | VARCHAR(255) |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `employeePayrolls` | OneToMany | EmployeePayroll | inverse | — | — | — | — | false | mappedBy `payroll_group` |

#### `PayrollCalculationConfig` → **`payroll_calculation_config`**

Single-row global config, read with `findOneBy([], ['id'=>'ASC'])`. Only one column.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `no_hours_per_week` | `no_hours_per_week` | `float` | — | No | No | — | DOUBLE PRECISION. The only tunable payroll constant in the DB |

#### `SalaryAdjustment` → **`salary_adjustment`**

OneToOne extension of a payslip holding 16 adjustment amounts (all `float`).

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `daily_rate` | `daily_rate` | `float` | — | No | No | — | DOUBLE PRECISION |
| `regular_days` | `regular_days` | `float` | — | No | No | — | DOUBLE PRECISION |
| `regular_days_pay` | `regular_days_pay` | `float` | — | No | No | — | DOUBLE PRECISION |
| `regular_ndot_hours` | `regular_ndot_hours` | `float` | — | No | No | — | DOUBLE PRECISION |
| `ot_meal_subsidy` | `ot_meal_subsidy` | `float` | — | No | No | — | DOUBLE PRECISION |
| `ot_meal_subsidy_amount` | `ot_meal_subsidy_amount` | `float` | — | No | No | — | DOUBLE PRECISION |
| `above_four_hours` | `above_four_hours` | `float` | — | No | No | — | DOUBLE PRECISION |
| `above_four_hours_amount` | `above_four_hours_amount` | `float` | — | No | No | — | DOUBLE PRECISION |
| `temp_allowance_amount` | `temp_allowance_amount` | `float` | — | No | No | — | DOUBLE PRECISION |
| `wellness` | `wellness` | `float` | — | No | No | — | DOUBLE PRECISION |
| `salary_adjustment` | `salary_adjustment` | `float` | — | No | No | — | DOUBLE PRECISION |
| `total_salary_adjustment` | `total_salary_adjustment` | `float` | — | No | No | — | DOUBLE PRECISION |
| `regular_ndot_amount` | `regular_ndot_amount` | `float` | — | Yes | No | — | DOUBLE PRECISION |
| `total_nontax_sal_adjustment` | `total_nontax_sal_adjustment` | `float` | — | No | No | — | DOUBLE PRECISION |
| `total_taxable_sal_adjustment` | `total_taxable_sal_adjustment` | `float` | — | No | No | — | DOUBLE PRECISION |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `payroll` | OneToOne | EmployeePayroll | owning | `payroll_id` | NULL (implicit) | — | persist, remove | false | inversedBy `salaryAdjustment` |

#### `TaxShield` → **`tax_shield`**

OneToOne extension of a payslip: non-taxable allowance carve-out.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `monthly_tax_shield` | `monthly_tax_shield` | `float` | — | No | No | — | DOUBLE PRECISION |
| `daily_tax_shield` | `daily_tax_shield` | `float` | — | No | No | — | DOUBLE PRECISION |
| `Remarks` | `remarks` | `string` | 255 | Yes | No | — | VARCHAR(255). **PascalCase property** → column `remarks` (underscore() lowercases; no split because `R` is at position 0) |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `payroll` | OneToOne | EmployeePayroll | owning | `payroll_id` | NULL (implicit) | — | persist, remove | false | inversedBy `taxShield` |

#### `ThirteenthMonthPayConfig` → **`thirteenth_month_pay_config`**

Superseded by the three `include_*_for_thirteenth_month` booleans on `EmployeePayrollProfile`. **Dead** — see §6.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `include_salary_adjustment` | `include_salary_adjustment` | `boolean` | — | No | No | — | TINYINT(1) |
| `include_salary` | `include_salary` | `boolean` | — | No | No | — | TINYINT(1) |
| `include_tax_shield_pay` | `include_tax_shield_pay` | `boolean` | — | No | No | — | TINYINT(1) |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `employee_payroll_profile` | OneToOne | EmployeePayrollProfile | owning | `employee_payroll_profile_id` | NULL (implicit) | — | persist, remove | false | inversedBy `thirteenthMonthPayConfig` |

#### `CashAdvance` → **`cash_advance`**

Active cash-advance agreement.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `cash_advance_amount` | `cash_advance_amount` | `float` | — | No | No | — | DOUBLE PRECISION |
| `cash_advance_deduction` | `cash_advance_deduction` | `float` | — | No | No | — | DOUBLE PRECISION |
| `date_start` | `date_start` | `date` | — | No | No | — | DATE |
| `remarks` | `remarks` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `starting_amount` | `starting_amount` | `float` | — | No | No | — | DOUBLE PRECISION |
| `enabled` | `enabled` | `boolean` | — | Yes | No | — | TINYINT(1). Nullable boolean acting as active flag |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `payroll_profile` | ManyToOne | EmployeePayrollProfile | owning | `payroll_profile_id` | NULL (implicit) | — | — | false | inversedBy `cashAdvances` |
| `cashAdvanceHistories` | OneToMany | CashAdvanceHistory | inverse | — | — | — | — | false | mappedBy `cash_advance` |

#### `CashAdvanceHistory` → **`cash_advance_history`**

Per-payroll amortisation ledger for a cash advance. Denormalises `payroll_profile_id` alongside `cash_advance_id`.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `remarks` | `remarks` | `string` | 255 | No | No | — | VARCHAR(255) |
| `previous_amount` | `previous_amount` | `float` | — | No | No | — | DOUBLE PRECISION |
| `deduction` | `deduction` | `float` | — | No | No | — | DOUBLE PRECISION |
| `current_amount` | `current_amount` | `float` | — | No | No | — | DOUBLE PRECISION |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `payroll_profile` | ManyToOne | EmployeePayrollProfile | owning | `payroll_profile_id` | NULL (implicit) | — | — | false | inversedBy `cashAdvanceHistories` |
| `cash_advance` | ManyToOne | CashAdvance | owning | `cash_advance_id` | NULL (implicit) | — | — | false | inversedBy `cashAdvanceHistories` |
| `payroll` | ManyToOne | EmployeePayroll | owning | `payroll_id` | NULL (implicit) | — | — | false | inversedBy `cashAdvanceHistories` |

#### `LoanHistory` → **`loan_history`**

Point-in-time snapshot of ALL eight loan balances for an employee. Superseded by the per-loan `*_history` tables but still written.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `sss_loan` | `sss_loan` | `float` | — | No | No | — | DOUBLE PRECISION |
| `sss_loan_deduction` | `sss_loan_deduction` | `float` | — | No | No | — | DOUBLE PRECISION |
| `hdmf_loan` | `hdmf_loan` | `float` | — | No | No | — | DOUBLE PRECISION |
| `hdmf_loan_deduction` | `hdmf_loan_deduction` | `float` | — | No | No | — | DOUBLE PRECISION |
| `cash_advance` | `cash_advance` | `float` | — | No | No | — | DOUBLE PRECISION |
| `cash_advance_deduction` | `cash_advance_deduction` | `float` | — | No | No | — | DOUBLE PRECISION |
| `other_loans` | `other_loans` | `float` | — | No | No | — | DOUBLE PRECISION |
| `other_loans_deduction` | `other_loans_deduction` | `float` | — | No | No | — | DOUBLE PRECISION |
| `createdAt` | `created_at` | `datetime_immutable` | — | No | No | — | DATETIME. camelCase property → column `created_at`. The only camelCase timestamp in the payroll domain |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `employee_record` | ManyToOne | EmployeeRecords | owning | `employee_record_id` | NULL (implicit) | — | — | false | inversedBy `loanHistories` |

#### `SSSLoans` → **`sssloans`**

SSS salary/calamity loan agreement.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `remark` | `remark` | `string` | 255 | No | No | — | VARCHAR(255) |
| `amount` | `amount` | `float` | — | No | No | — | DOUBLE PRECISION |
| `deduction` | `deduction` | `float` | — | No | No | — | DOUBLE PRECISION |
| `date` | `date` | `date` | — | No | No | — | DATE |
| `enabled` | `enabled` | `boolean` | — | Yes | No | — | TINYINT(1) |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `payroll_profile` | ManyToOne | EmployeePayrollProfile | owning | `payroll_profile_id` | NULL (implicit) | — | — | false | inversedBy `sss_loans` |
| `sSSLoansHistories` | OneToMany | SSSLoansHistory | inverse | — | — | — | — | false | mappedBy `sss_loan` |

#### `SSSLoansHistory` → **`sssloans_history`**

SSS loan amortisation ledger.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `remark` | `remark` | `string` | 255 | No | No | — | VARCHAR(255) |
| `previous_amount` | `previous_amount` | `float` | — | No | No | — | DOUBLE PRECISION |
| `deduction` | `deduction` | `float` | — | No | No | — | DOUBLE PRECISION |
| `date` | `date` | `datetime` | — | No | No | — | DATETIME. `DATETIME` here but `DATE` on the equivalent `pagibig_loans_history.date` — inconsistent |
| `current_amount` | `current_amount` | `float` | — | No | No | — | DOUBLE PRECISION |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `payroll_profile` | ManyToOne | EmployeePayrollProfile | owning | `payroll_profile_id` | NULL (implicit) | — | — | false | inversedBy `sSSLoansHistories` |
| `sss_loan` | ManyToOne | SSSLoans | owning | `sss_loan_id` | NULL (implicit) | — | — | false | inversedBy `sSSLoansHistories` |

#### `PagibigLoans` → **`pagibig_loans`**

HDMF/Pag-IBIG loan agreement.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `remark` | `remark` | `string` | 255 | No | No | — | VARCHAR(255) |
| `amount` | `amount` | `float` | — | No | No | — | DOUBLE PRECISION |
| `deduction` | `deduction` | `float` | — | No | No | — | DOUBLE PRECISION |
| `date` | `date` | `date` | — | No | No | — | DATE |
| `enabled` | `enabled` | `boolean` | — | Yes | No | — | TINYINT(1) |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `payroll_profile` | ManyToOne | EmployeePayrollProfile | owning | `payroll_profile_id` | NULL (implicit) | — | — | false | inversedBy `pagibigLoans` |
| `pagibigLoansHistories` | OneToMany | PagibigLoansHistory | inverse | — | — | — | — | false | mappedBy `pagibig_loans_history` |

#### `PagibigLoansHistory` → **`pagibig_loans_history`**

Pag-IBIG loan amortisation ledger.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `remark` | `remark` | `string` | 255 | No | No | — | VARCHAR(255) |
| `previous_amount` | `previous_amount` | `float` | — | No | No | — | DOUBLE PRECISION |
| `current_amount` | `current_amount` | `float` | — | No | No | — | DOUBLE PRECISION |
| `deduction` | `deduction` | `float` | — | No | No | — | DOUBLE PRECISION |
| `date` | `date` | `date` | — | No | No | — | DATE |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `payroll_profile` | ManyToOne | EmployeePayrollProfile | owning | `payroll_profile_id` | NULL (implicit) | — | — | false | inversedBy `pagibigLoansHistories` |
| `pagibig_loans_history` | ManyToOne | PagibigLoans | owning | `pagibig_loans_history_id` | NULL (implicit) | — | — | false | inversedBy `pagibigLoansHistories` |

### 3c. Government contributions

#### `SSSConfig` → **`sssconfig`**

SSS contribution bracket table (2023 MSC/WISP structure). One row per salary range.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `range_start` | `range_start` | `float` | — | No | No | — | DOUBLE PRECISION. Salary bracket lower bound |
| `range_end` | `range_end` | `float` | — | No | No | — | DOUBLE PRECISION |
| `msc_ec` | `msc_ec` | `float` | — | No | No | — | DOUBLE PRECISION |
| `msc_wisp` | `msc_wisp` | `float` | — | No | No | — | DOUBLE PRECISION |
| `msc_total` | `msc_total` | `float` | — | No | No | — | DOUBLE PRECISION |
| `contribution_regular_er` | `contribution_regular_er` | `float` | — | No | No | — | DOUBLE PRECISION |
| `contribution_regular_ee` | `contribution_regular_ee` | `float` | — | No | No | — | DOUBLE PRECISION |
| `contribution_ec_er` | `contribution_ec_er` | `float` | — | No | No | — | DOUBLE PRECISION |
| `contribution_ec_ee` | `contribution_ec_ee` | `float` | — | No | No | — | DOUBLE PRECISION |
| `contribution_wisp_er` | `contribution_wisp_er` | `float` | — | No | No | — | DOUBLE PRECISION |
| `contribution_wisp_ee` | `contribution_wisp_ee` | `float` | — | No | No | — | DOUBLE PRECISION |
| `contribution_total_er` | `contribution_total_er` | `float` | — | No | No | — | DOUBLE PRECISION |
| `contribution_total_ee` | `contribution_total_ee` | `float` | — | No | No | — | DOUBLE PRECISION |
| `isArchived` | `is_archived` | `boolean` | — | Yes | No | — | TINYINT(1). camelCase → column `is_archived`, added by migration 2.3 |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `employeePayrollProfiles` | OneToMany | EmployeePayrollProfile | inverse | — | — | — | — | false | mappedBy `sss_contribution` |

#### `PhilHealthConfig` → **`phil_health_config`**

PhilHealth premium configuration. Expected to be a single active row.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `base_rate` | `base_rate` | `float` | — | No | No | — | DOUBLE PRECISION |
| `employee_share` | `employee_share` | `float` | — | No | No | — | DOUBLE PRECISION |
| `employer_share` | `employer_share` | `float` | — | No | No | — | DOUBLE PRECISION |
| `minimum_cap` | `minimum_cap` | `float` | — | No | No | — | DOUBLE PRECISION |
| `maximum_cap` | `maximum_cap` | `float` | — | No | No | — | DOUBLE PRECISION |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `employeePayrollProfiles` | OneToMany | EmployeePayrollProfile | inverse | — | — | — | — | false | mappedBy `philhealth_contribution` |

#### `PagibigConfig` → **`pagibig_config`**

Pag-IBIG (HDMF) contribution configuration.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `employer_share` | `employer_share` | `float` | — | No | No | — | DOUBLE PRECISION |
| `employee_share` | `employee_share` | `float` | — | No | No | — | DOUBLE PRECISION |
| `monthly_compensation_cap` | `monthly_compensation_cap` | `float` | — | No | No | — | DOUBLE PRECISION |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `employeePayrollProfiles` | OneToMany | EmployeePayrollProfile | inverse | — | — | — | — | false | mappedBy `pagibig_contribution` |

#### `TaxConfig` → **`tax_config`**

BIR withholding-tax bracket table.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `tax_bracket_name` | `tax_bracket_name` | `string` | 255 | No | No | — | VARCHAR(255) |
| `tax_bracket_range` | `tax_bracket_range` | `float` | — | No | No | — | DOUBLE PRECISION. Bracket **lower** bound (badly named — `_range` vs `_range_end`) |
| `tax_bracket_range_end` | `tax_bracket_range_end` | `float` | — | No | No | — | DOUBLE PRECISION |
| `tax_deduction_percent` | `tax_deduction_percent` | `float` | — | No | No | — | DOUBLE PRECISION |
| `tax_deduction_amount` | `tax_deduction_amount` | `float` | — | No | No | — | DOUBLE PRECISION |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `employeePayrollProfiles` | OneToMany | EmployeePayrollProfile | inverse | — | — | — | — | false | mappedBy `tax_contribution` |

### 3d. Attendance / DTR / Shifts

#### `Worker` → **`worker`**

Biometric-device identity, imported from the external attendance DB. Bridges to `EmployeeRecords` via `emp_record_id`.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `workerId` | `worker_id` | `string` | 255 | No | No | — | VARCHAR(255). camelCase → column `worker_id`. The device-side user id |
| `firstname` | `firstname` | `string` | 255 | No | No | — | VARCHAR(255) |
| `lastname` | `lastname` | `string` | 255 | No | No | — | VARCHAR(255) |
| `position` | `position` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `workerDocs` | `worker_docs` | `string` | 255 | Yes | No | — | VARCHAR(255). camelCase → column `worker_docs` |
| `photo` | `photo` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `erName` | `er_name` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `erContact` | `er_contact` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `status` | `status` | `string` | 255 | Yes | No | — | VARCHAR(255). Free text passed straight through from the biometric DB |
| `empcode` | `empcode` | `string` | 255 | Yes | No | — | VARCHAR(255). Denormalised copy of `employee_records.employee_code` — all lowercase, so column is `empcode` |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `workerLog` | OneToMany | WorkerLogs | inverse | — | — | — | — | false | mappedBy `user` |
| `emp_record` | ManyToOne | EmployeeRecords | owning | `emp_record_id` | NULL (implicit) | — | — | false | inversedBy `workers` |

#### `WorkerLogs` → **`worker_logs`**

The DTR table: one row per worker per day, with time-in/out and computed hours.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `type` | `type` | `string` | 255 | Yes | No | — | VARCHAR(255). Free text passed straight through from the biometric source row |
| `loginDate` | `login_date` | `datetime` | — | Yes | No | — | DATETIME. camelCase → column `login_date`. Time-IN (DATETIME) |
| `logoutDate` | `logout_date` | `datetime` | — | Yes | No | — | DATETIME. camelCase → column `logout_date`. Time-OUT (DATETIME) |
| `worker_log_id` | `worker_log_id` | `string` | 255 | Yes | No | — | VARCHAR(255). **VARCHAR** copy of the source-system primary key — the idempotency key for sync, unindexed |
| `overtime` | `overtime` | `float` | — | Yes | No | — | DOUBLE PRECISION. Minutes (float) despite the name suggesting hours |
| `overtime_approved` | `overtime_approved` | `boolean` | — | Yes | No | — | TINYINT(1) |
| `undertime` | `undertime` | `float` | — | Yes | No | — | DOUBLE PRECISION. Minutes (float) |
| `rendered_hours` | `rendered_hours` | `float` | — | Yes | No | — | DOUBLE PRECISION. Actually stores **minutes** (`setRenderedHours($totalMinutesDifference)`) — name lies |
| `is_time_calculated` | `is_time_calculated` | `boolean` | — | No | No | — | TINYINT(1). **NOT NULL** boolean; guards recomputation during sync |
| `created_at` | `created_at` | `datetime_immutable` | — | Yes | No | — | DATETIME |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `user` | ManyToOne | Worker | owning | `user_id` | NOT NULL | — | — | false | inversedBy `workerLog` |
| `attendance_status` | ManyToOne | AttendanceTypes | owning | `attendance_status_id` | NULL (implicit) | — | — | false | inversedBy `yes` |
| `empTasks` | OneToMany | EmpTask | inverse | — | — | — | — | false | mappedBy `worker_logs` |
| `employeeOvertimeRequests` | OneToMany | EmployeeOvertimeRequest | inverse | — | — | — | — | false | mappedBy `worker_logs` |
| `dTRAdjutments` | OneToMany | DTRAdjutments | inverse | — | — | — | — | false | mappedBy `worker_logs` |

#### `AttendanceTypes` → **`attendance_types`**

Lookup for DTR day classification (Present/Absent/…).

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `name` | `name` | `string` | 255 | No | No | — | VARCHAR(255) |
| `is_hours_rendered` | `is_hours_rendered` | `boolean` | — | No | No | — | TINYINT(1) |
| `hours_provided` | `hours_provided` | `float` | — | Yes | No | — | DOUBLE PRECISION |
| `automated_attendance` | `automated_attendance` | `boolean` | — | Yes | No | — | TINYINT(1). Exactly one row is expected to have this true; used as the default type during sync |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `yes` | OneToMany | WorkerLogs | inverse | — | — | — | — | false | mappedBy `attendance_status` |

#### `DTRAdjutments` → **`dtradjutments`**

**Typo in the class name** (`Adjutments`), which propagates to table `dtradjutments`. Records that a DTR row was manually adjusted on a given date.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `adjusted_date` | `adjusted_date` | `date` | — | No | No | — | DATE |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `worker_logs` | ManyToOne | WorkerLogs | owning | `worker_logs_id` | NULL (implicit) | — | — | false | inversedBy `dTRAdjutments` |
| `emp_record` | ManyToOne | EmployeeRecords | owning | `emp_record_id` | NULL (implicit) | — | — | false | inversedBy `dTRAdjutments` |

#### `EmployeeOvertimeRequest` → **`employee_overtime_request`**

OT approval workflow attached to a `WorkerLogs` row.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `status` | `status` | `smallint` | — | No | No | — | SMALLINT. Implicit enum 0/1/2, see §4 |
| `time_requested` | `time_requested` | `float` | — | No | No | — | DOUBLE PRECISION. Hours requested (float) |
| `reason` | `reason` | `string` | 255 | Yes | No | — | VARCHAR(255) |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `emp_id` | ManyToOne | EmployeeRecords | owning | `emp_id_id` | NULL (implicit) | — | — | false | inversedBy `employeeOvertimeRequests` |
| `worker_logs` | ManyToOne | WorkerLogs | owning | `worker_logs_id` | NULL (implicit) | — | — | false | inversedBy `employeeOvertimeRequests` |
| `approved_by` | ManyToOne | EmployeeRecords | owning | `approved_by_id` | NULL (implicit) | — | — | false | inversedBy `employeeOvertimeRequests` |

#### `Shifts` → **`shifts`**

Work-shift definition assigned to `User`.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `start_time` | `start_time` | `time` | — | Yes | No | — | TIME |
| `end_time` | `end_time` | `time` | — | Yes | No | — | TIME |
| `archived` | `archived` | `boolean` | — | Yes | No | — | TINYINT(1) |
| `name` | `name` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `lunch_break_duration` | `lunch_break_duration` | `float` | — | Yes | No | — | DOUBLE PRECISION |
| `total_hours_minus_lunch` | `total_hours_minus_lunch` | `float` | — | Yes | No | — | DOUBLE PRECISION. Read as **minutes** in `SyncWorkerController` (`$empShiftHours = 480`) — name says hours |
| `days_of_week` | `days_of_week` | `array` | — | Yes | No | — | LONGTEXT (DC2Type:array). `Types::ARRAY` → **PHP-serialised LONGTEXT**, not JSON |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `users` | OneToMany | User | inverse | — | — | — | — | false | mappedBy `emp_shift` |

#### `HolidayConfig` → **`holiday_config`**

Holiday template (name + multipliers). Has **no `type` column** — see §4.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `name` | `name` | `string` | 255 | No | No | — | VARCHAR(255) |
| `date` | `date` | `date` | — | No | No | — | DATE. The template's canonical date; per-year instances live in `yearly_holiday` |
| `multiplier_regular` | `multiplier_regular` | `float` | — | No | No | — | DOUBLE PRECISION |
| `multiplier_overtime` | `multiplier_overtime` | `float` | — | No | No | — | DOUBLE PRECISION |
| `archived` | `archived` | `boolean` | — | Yes | No | — | TINYINT(1). Added by migration 2.2 |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `yearlyHolidays` | OneToMany | YearlyHoliday | inverse | — | — | — | — | false | mappedBy `holiday_config` |

#### `YearlyHoliday` → **`yearly_holiday`**

Per-year materialisation of a `HolidayConfig`.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `date` | `date` | `date` | — | Yes | No | — | DATE |
| `year` | `year` | `string` | 255 | No | No | — | VARCHAR(255). Year stored as **VARCHAR(255)** |
| `archived` | `archived` | `boolean` | — | Yes | No | — | TINYINT(1) |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `holiday_config` | ManyToOne | HolidayConfig | owning | `holiday_config_id` | NOT NULL | — | — | false | inversedBy `yearlyHolidays` |

### 3e. Leave

#### `LeavePolicy` → **`leave_policy`**

Leave-type definition with eligibility rules.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `name` | `name` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `year` | `year` | `string` | 255 | Yes | No | — | VARCHAR(255). VARCHAR(255), nullable since migration 2.1 |
| `description` | `description` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `days` | `days` | `float` | — | No | No | — | DOUBLE PRECISION. Default entitlement in days |
| `calendar_color` | `calendar_color` | `string` | 255 | No | No | — | VARCHAR(255) |
| `type` | `type` | `string` | 255 | Yes | No | — | VARCHAR(255). Nullable free text; the UI field is **commented out** in `leave_policy.html.twig` — effectively unused |
| `gender` | `gender` | `string` | 255 | Yes | No | — | VARCHAR(255). **VARCHAR** holding the numeric codes 0/1/2/3 — see §4. Made nullable by migrations 2.1/2.2 |
| `marital` | `marital` | `smallint` | — | No | No | — | SMALLINT. **SMALLINT** holding 0/1/2/3 — inconsistent storage type vs `gender` |
| `increment_amount` | `increment_amount` | `integer` | — | No | No | — | INT |
| `years_before_increment` | `years_before_increment` | `integer` | — | No | No | — | INT |
| `is_carried_over` | `is_carried_over` | `boolean` | — | No | No | — | TINYINT(1) |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `department` | ManyToOne | Department | owning | `department_id` | NULL (implicit) | — | — | false | inversedBy `leavePolicies` |
| `leaveRequests` | OneToMany | LeaveRequest | inverse | — | — | — | — | false | mappedBy `leave_policies` |
| `yearlyEmployeeLeaves` | ManyToMany | YearlyEmployeeLeave | inverse | — | — | — | — | false | mappedBy `selected_leave_policies` |
| `selectedEmployeeLeaves` | OneToMany | SelectedEmployeeLeaves | inverse | — | — | — | — | false | mappedBy `leave_policy` |

#### `LeaveRequest` → **`leave_request`**

A single leave application.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `reason` | `reason` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `date_start` | `date_start` | `datetime` | — | No | No | — | DATETIME |
| `date_end` | `date_end` | `datetime` | — | No | No | — | DATETIME |
| `is_half_day` | `is_half_day` | `boolean` | — | No | No | — | TINYINT(1) |
| `document` | `document` | `string` | 255 | No | No | — | VARCHAR(255). **NOT NULL** VARCHAR — a supporting document path is mandatory at DB level |
| `year` | `year` | `string` | 255 | No | No | — | VARCHAR(255). VARCHAR(255) |
| `status` | `status` | `string` | 255 | No | No | — | VARCHAR(255). **VARCHAR(255)** holding `'0'`/`'1'`/`'2'` — see §4. NOT NULL with no default; controller sets `0` on create |
| `created_at` | `created_at` | `datetime_immutable` | — | No | No | — | DATETIME. `datetime_immutable`; set manually |
| `total_days_requested` | `total_days_requested` | `float` | — | No | No | — | DOUBLE PRECISION |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `emp_record` | ManyToOne | EmployeeRecords | owning | `emp_record_id` | NOT NULL | — | — | false | inversedBy `leaveRequests` |
| `leave_policies` | ManyToOne | LeavePolicy | owning | `leave_policies_id` | NOT NULL | — | — | false | inversedBy `leaveRequests` |
| `updated_by` | ManyToOne | EmployeeRecords | owning | `updated_by_id` | NULL (implicit) | — | — | false | inversedBy `leaveRequests` |
| `selected_leave` | ManyToOne | SelectedEmployeeLeaves | owning | `selected_leave_id` | NULL (implicit) | — | — | false | inversedBy `leaveRequests` |

#### `YearlyEmployeeLeave` → **`yearly_employee_leave`**

Per-employee, per-year leave ledger header.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `year` | `year` | `string` | 255 | No | No | — | VARCHAR(255) |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `emp_record` | ManyToOne | EmployeeRecords | owning | `emp_record_id` | NOT NULL | — | — | false | inversedBy `yearlyEmployeeLeaves` |
| `selectedEmployeeLeaves` | OneToMany | SelectedEmployeeLeaves | inverse | — | — | — | — | false | mappedBy `employee_leave` |

#### `SelectedEmployeeLeaves` → **`selected_employee_leaves`**

Per-employee, per-policy leave balance line.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `no_of_days` | `no_of_days` | `float` | — | No | No | — | DOUBLE PRECISION |
| `used_days` | `used_days` | `float` | — | No | No | — | DOUBLE PRECISION |
| `carried_over_days` | `carried_over_days` | `float` | — | No | No | — | DOUBLE PRECISION |
| `carry_over_policy` | `carry_over_policy` | `integer` | — | No | No | — | INT. Implicit enum 0–3, see §4 |
| `status` | `status` | `integer` | — | No | No | — | INT. Implicit enum 0=Enabled / 1=Disabled — **inverted** relative to every other status column, see §4 |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `leave_policy` | ManyToOne | LeavePolicy | owning | `leave_policy_id` | NULL (implicit) | — | — | false | inversedBy `selectedEmployeeLeaves` |
| `employee_leave` | ManyToOne | YearlyEmployeeLeave | owning | `employee_leave_id` | NULL (implicit) | — | — | false | inversedBy `selectedEmployeeLeaves` |
| `leaveRequests` | OneToMany | LeaveRequest | inverse | — | — | — | — | false | mappedBy `selected_leave` |

### 3f. Projects / Manpower / Construction

#### `Project` → **`project`**

Construction project.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `code` | `code` | `string` | 255 | No | No | — | VARCHAR(255) |
| `name` | `name` | `string` | 255 | No | No | — | VARCHAR(255) |
| `description` | `description` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `archived` | `archived` | `boolean` | — | Yes | No | — | TINYINT(1) |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `subdivision` | ManyToOne | Subdivision | owning | `subdivision_id` | NULL (implicit) | — | — | false | inversedBy `project` |
| `categories` | OneToMany | Category | inverse | — | — | — | — | false | mappedBy `project` |
| `project_type` | ManyToOne | ProjectType | owning | `project_type_id` | NULL (implicit) | — | — | false | inversedBy `projects` |
| `employeeProjects` | OneToMany | EmployeeProjects | inverse | — | — | — | — | false | mappedBy `project` |

#### `ProjectType` → **`project_type`**

Lookup referenced only by `Project.project_type`; **no controller ever reads or writes it** — see §6.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `project_name` | `project_name` | `string` | 255 | No | No | — | VARCHAR(255) |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `projects` | OneToMany | Project | inverse | — | — | — | — | false | mappedBy `project_type` |

#### `Subdivision` → **`subdivision`**

Top of the construction location hierarchy: Subdivision → Phase → Blocks → Lots → Category.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `subdivision_code` | `subdivision_code` | `string` | 255 | No | No | — | VARCHAR(255) |
| `description` | `description` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `name` | `name` | `string` | 255 | No | No | — | VARCHAR(255) |
| `archived` | `archived` | `boolean` | — | Yes | No | — | TINYINT(1) |
| `location` | `location` | `string` | 255 | No | No | — | VARCHAR(255) |
| `total_lots` | `total_lots` | `integer` | — | No | No | — | INT. **Denormalised** count, never recomputed |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `project` | OneToMany | Project | inverse | — | — | — | — | false | mappedBy `subdivision` |
| `phases` | OneToMany | Phase | inverse | — | — | — | — | false | mappedBy `subdivision` |

#### `Phase` → **`phase`**

Second level of the location hierarchy.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `name` | `name` | `string` | 255 | No | No | — | VARCHAR(255) |
| `code` | `code` | `string` | 255 | No | No | — | VARCHAR(255) |
| `total_blocks` | `total_blocks` | `integer` | — | No | No | — | INT. Denormalised count |
| `total_lots` | `total_lots` | `integer` | — | No | No | — | INT. Denormalised count |
| `archived` | `archived` | `boolean` | — | Yes | No | — | TINYINT(1) |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `subdivision` | ManyToOne | Subdivision | owning | `subdivision_id` | NOT NULL | — | — | false | inversedBy `phases` |
| `categories` | OneToMany | Category | inverse | — | — | — | — | false | mappedBy `phase` |
| `blocks` | OneToMany | Blocks | inverse | — | — | — | — | false | mappedBy `phase` |

#### `Blocks` → **`blocks`**

Third level. Plural class name → plural table.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `block_name` | `block_name` | `string` | 255 | No | No | — | VARCHAR(255) |
| `total_lots` | `total_lots` | `integer` | — | No | No | — | INT. Denormalised count |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `phase` | ManyToOne | Phase | owning | `phase_id` | NOT NULL | — | — | false | inversedBy `blocks` |
| `categories` | OneToMany | Category | inverse | — | — | — | — | false | mappedBy `blocks` |
| `lots` | OneToMany | Lots | inverse | — | — | — | — | false | mappedBy `blocks` |

#### `Lots` → **`lots`**

Fourth level. Plural class name → plural table.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `lot_num` | `lot_num` | `integer` | — | Yes | No | — | INT |
| `lot_name` | `lot_name` | `string` | 255 | Yes | No | — | VARCHAR(255) |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `blocks` | ManyToOne | Blocks | owning | `blocks_id` | NULL (implicit) | — | — | false | inversedBy `lots` |
| `category` | OneToOne | Category | inverse | — | — | — | persist, remove | false | mappedBy `lots` |

#### `Category` → **`category`**

The saleable house-and-lot unit: joins Project + Phase + Blocks + Lots + Model + Owner.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `code` | `code` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `description` | `description` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `location` | `location` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `block` | `block` | `integer` | — | Yes | No | — | INT. **Redundant scalar `int`** duplicating `blocks_id` |
| `lot` | `lot` | `integer` | — | Yes | No | — | INT. **Redundant scalar `int`** duplicating `lots_id` |
| `archived` | `archived` | `boolean` | — | Yes | No | — | TINYINT(1) |
| `isOverhead` | `is_overhead` | `boolean` | — | Yes | No | — | TINYINT(1). camelCase → column `is_overhead` |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `project` | ManyToOne | Project | owning | `project_id` | NOT NULL | — | — | false | inversedBy `categories` |
| `model` | ManyToOne | Model | owning | `model_id` | NULL (implicit) | — | — | false | inversedBy `categories` |
| `phase` | ManyToOne | Phase | owning | `phase_id` | NOT NULL | — | — | false | inversedBy `categories` |
| `blocks` | ManyToOne | Blocks | owning | `blocks_id` | NULL | — | — | false | inversedBy `categories` |
| `owner` | ManyToOne | Owner | owning | `owner_id` | NULL (implicit) | — | — | false | inversedBy `categories` |
| `lots` | OneToOne | Lots | owning | `lots_id` | NULL (implicit) | — | persist, remove | false | inversedBy `category` |

#### `Model` → **`model`**

House model.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `name` | `name` | `string` | 255 | No | No | — | VARCHAR(255) |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `categories` | OneToMany | Category | inverse | — | — | — | — | false | mappedBy `model` |
| `type` | ManyToOne | ModelTypes | owning | `type_id` | NULL | — | — | false | inversedBy `models` |

#### `ModelTypes` → **`model_types`**

Lookup for house-model types.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `name` | `name` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `code` | `code` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `archived` | `archived` | `boolean` | — | Yes | No | — | TINYINT(1) |
| `additional_options` | `additional_options` | `boolean` | — | Yes | No | — | TINYINT(1) |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `models` | OneToMany | Model | inverse | — | — | — | — | false | mappedBy `type` |

#### `Owner` → **`owner`**

Buyer/owner of a Category. **Denormalised address**: stores `lot_no`/`block` as strings instead of FKs.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `firstname` | `firstname` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `lastname` | `lastname` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `lot_no` | `lot_no` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `block` | `block` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `email` | `email` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `contact_no` | `contact_no` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `archived` | `archived` | `boolean` | — | Yes | No | — | TINYINT(1) |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `categories` | OneToMany | Category | inverse | — | — | — | — | false | mappedBy `owner` |

#### `EmployeeProjects` → **`employee_projects`**

Assignment of an employee to a project.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `Date` | `date` | `datetime` | — | Yes | No | — | DATETIME. **PascalCase property `$Date`** → column `date`. Only PascalCase field in the schema besides `TaxShield.Remarks` |
| `rendered_hours` | `rendered_hours` | `integer` | — | Yes | No | — | INT. `int` here, but `float` on `EmpTask.assigned_hours` — inconsistent |
| `task` | `task` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `archived` | `archived` | `boolean` | — | Yes | No | — | TINYINT(1) |
| `is_assigned` | `is_assigned` | `boolean` | — | Yes | No | — | TINYINT(1) |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `project` | ManyToOne | Project | owning | `project_id` | NULL (implicit) | — | — | false | inversedBy `employeeProjects` |
| `employee` | ManyToOne | EmployeeRecords | owning | `employee_id` | NULL (implicit) | — | — | false | inversedBy `employeeProjects` |
| `empTasks` | OneToMany | EmpTask | inverse | — | — | — | — | false | mappedBy `emp_project` |

#### `EmpTask` → **`emp_task`**

Timesheet line: hours an employee booked against a project assignment on a date.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `task_desc` | `task_desc` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `rendered_hours` | `rendered_hours` | `integer` | — | Yes | No | — | INT. `int` |
| `date` | `date` | `datetime` | — | Yes | No | — | DATETIME |
| `archived` | `archived` | `boolean` | — | Yes | No | — | TINYINT(1) |
| `approved` | `approved` | `boolean` | — | Yes | No | — | TINYINT(1) |
| `assigned_hours` | `assigned_hours` | `float` | — | Yes | No | — | DOUBLE PRECISION. `float` |
| `is_adjusted` | `is_adjusted` | `boolean` | — | Yes | No | — | TINYINT(1) |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `emp_project` | ManyToOne | EmployeeProjects | owning | `emp_project_id` | NULL (implicit) | — | — | false | inversedBy `empTasks` |
| `worker_logs` | ManyToOne | WorkerLogs | owning | `worker_logs_id` | NULL (implicit) | — | — | false | inversedBy `empTasks` |

### 3g. Auth / RBAC

#### `User` → **`user`**

Login account. Implements `PasswordAuthenticatedUserInterface`/`UserInterface`. **No unique constraint on `email` or `username`** — the `#[ORM\UniqueConstraint]` line is commented out.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `email` | `email` | `string` | 180 | No | No | — | VARCHAR(180). VARCHAR(180) — the classic maker-bundle length, but the UNIQUE index is commented out |
| `roles` | `roles` | `json` | — | No | No | — | JSON. `json` column. Symfony security roles — *separate from and unused by* the real RBAC in `MainModules`/`SubModules` |
| `password` | `password` | `string` | 255 | No | No | — | VARCHAR(255) |
| `firstName` | `first_name` | `string` | 255 | Yes | No | — | VARCHAR(255). camelCase → `first_name`. **Duplicates `employee_records.first_name`** |
| `middleName` | `middle_name` | `string` | 255 | Yes | No | — | VARCHAR(255). camelCase → `middle_name`. Duplicates `employee_records.middle_name` |
| `lastName` | `last_name` | `string` | 255 | Yes | No | — | VARCHAR(255). camelCase → `last_name`. Duplicates `employee_records.last_name` |
| `birthdate` | `birthdate` | `date` | — | Yes | No | — | DATE. `date` here vs `datetime` on `EmployeeRecords.birthdate` — duplicated and typed differently |
| `gender` | `gender` | `string` | 255 | Yes | No | — | VARCHAR(255). Duplicates `employee_records.gender` |
| `address` | `address` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `contactNum` | `contact_num` | `string` | 50 | Yes | No | — | VARCHAR(50). camelCase → `contact_num`, VARCHAR(50). Accepted as a login identifier |
| `biometricData` | `biometric_data` | `string` | 999 | Yes | No | — | VARCHAR(999). camelCase → `biometric_data`, VARCHAR(999) |
| `status` | `status` | `integer` | — | Yes | No | — | INT. Nullable `integer`, semantics undocumented and unused in controllers |
| `userId` | `user_id` | `string` | 255 | Yes | No | — | VARCHAR(255). camelCase → `user_id`. Declared **non-nullable PHP type `string`** but `nullable: true` in the column — set to the literal `'test'` at registration |
| `removed` | `removed` | `integer` | — | No | No | — | INT. `integer` NOT NULL soft-delete flag — a *third* soft-delete convention (alongside `archived` and `isArchived`) |
| `profilePhoto` | `profile_photo` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `block` | `block` | `string` | 255 | Yes | No | — | VARCHAR(255). Address fragment duplicated from EmployeeRecords/Owner |
| `lot` | `lot` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `phase` | `phase` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `street` | `street` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `city` | `city` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `province` | `province` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `country` | `country` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `zip` | `zip` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `loginCount` | `login_count` | `integer` | — | Yes | No | — | INT. camelCase → `login_count`; never incremented anywhere |
| `username` | `username` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `archived` | `archived` | `boolean` | — | Yes | No | — | TINYINT(1). Nullable boolean soft delete — coexists with `removed` and `is_active` |
| `is_straight_time` | `is_straight_time` | `boolean` | — | Yes | No | — | TINYINT(1) |
| `is_assignable_proj` | `is_assignable_proj` | `boolean` | — | Yes | No | — | TINYINT(1) |
| `is_active` | `is_active` | `boolean` | — | Yes | No | — | TINYINT(1). Nullable boolean; the flag actually checked at login |
| `reset_token` | `reset_token` | `string` | 1000 | Yes | No | — | VARCHAR(1000). VARCHAR(1000), plain text password-reset token |
| `token_expiry` | `token_expiry` | `datetime` | — | Yes | No | — | DATETIME |
| `is_worker` | `is_worker` | `boolean` | — | Yes | No | — | TINYINT(1) |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `user_type` | ManyToOne | UserType | owning | `user_type_id` | NOT NULL | — | — | false | inversedBy `users` |
| `auditTrailLogs` | OneToMany | AuditTrailLog | inverse | — | — | — | — | false | mappedBy `user` |
| `employeeRecords` | OneToOne | EmployeeRecords | inverse | — | — | — | persist, remove | false | mappedBy `user` |
| `emp_shift` | ManyToOne | Shifts | owning | `emp_shift_id` | NULL (implicit) | — | — | false | inversedBy `users` |

#### `UserType` → **`user_type`**

Role. `user_code` is the short role code used throughout the frontend — see §4.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `name` | `name` | `string` | 255 | No | No | — | VARCHAR(255) |
| `removed` | `removed` | `smallint` | — | No | No | — | SMALLINT. SMALLINT NOT NULL soft-delete flag; written with a **boolean** (`setRemoved(false)`) in `LoginController` |
| `user_code` | `user_code` | `string` | 255 | No | No | — | VARCHAR(255) |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `users` | OneToMany | User | inverse | — | — | — | — | false | mappedBy `user_type` |
| `main_module` | OneToOne | MainModules | owning | `main_module_id` | NULL (implicit) | — | persist, remove | false | inversedBy `userType` |

#### `MainModules` → **`main_modules`**

Top-level RBAC permission bag: 5 `Types::ARRAY` (PHP-serialised) columns, one per main module.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `project` | `project` | `array` | — | Yes | No | — | LONGTEXT (DC2Type:array). PHP-serialised array of `can_*` flags |
| `humanres` | `humanres` | `array` | — | Yes | No | — | LONGTEXT (DC2Type:array) |
| `administration` | `administration` | `array` | — | Yes | No | — | LONGTEXT (DC2Type:array) |
| `payroll` | `payroll` | `array` | — | Yes | No | — | LONGTEXT (DC2Type:array). Declared `array` (not `?array`) but `nullable: true` — type/DDL mismatch |
| `emp_leaves` | `emp_leaves` | `array` | — | Yes | No | — | LONGTEXT (DC2Type:array). Declared `array` (not `?array`) but `nullable: true` |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `submodule` | OneToOne | SubModules | owning | `submodule_id` | NULL (implicit) | — | persist, remove | false | inversedBy `mainModules` |
| `userType` | OneToOne | UserType | inverse | — | — | — | persist, remove | false | mappedBy `main_module` |

#### `SubModules` → **`sub_modules`**

Sub-level RBAC permission bag: **25 `Types::ARRAY` (PHP-serialised) columns**, one per submodule. This is the permission matrix — see §4.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `daily_time_record` | `daily_time_record` | `array` | — | Yes | No | — | LONGTEXT (DC2Type:array) |
| `subdivision` | `subdivision` | `array` | — | Yes | No | — | LONGTEXT (DC2Type:array) |
| `division` | `division` | `array` | — | Yes | No | — | LONGTEXT (DC2Type:array) |
| `department` | `department` | `array` | — | Yes | No | — | LONGTEXT (DC2Type:array) |
| `phase` | `phase` | `array` | — | Yes | No | — | LONGTEXT (DC2Type:array) |
| `owner` | `owner` | `array` | — | Yes | No | — | LONGTEXT (DC2Type:array) |
| `models` | `models` | `array` | — | Yes | No | — | LONGTEXT (DC2Type:array) |
| `model_types` | `model_types` | `array` | — | Yes | No | — | LONGTEXT (DC2Type:array) |
| `emp_settings` | `emp_settings` | `array` | — | Yes | No | — | LONGTEXT (DC2Type:array) |
| `shifts` | `shifts` | `array` | — | Yes | No | — | LONGTEXT (DC2Type:array) |
| `projects` | `projects` | `array` | — | Yes | No | — | LONGTEXT (DC2Type:array) |
| `emp_project` | `emp_project` | `array` | — | Yes | No | — | LONGTEXT (DC2Type:array) |
| `emp_list` | `emp_list` | `array` | — | Yes | No | — | LONGTEXT (DC2Type:array) |
| `sss_config` | `sss_config` | `array` | — | Yes | No | — | LONGTEXT (DC2Type:array) |
| `pagibig_config` | `pagibig_config` | `array` | — | Yes | No | — | LONGTEXT (DC2Type:array) |
| `bir_config` | `bir_config` | `array` | — | Yes | No | — | LONGTEXT (DC2Type:array) |
| `philhealth_config` | `philhealth_config` | `array` | — | Yes | No | — | LONGTEXT (DC2Type:array) |
| `payroll` | `payroll` | `array` | — | Yes | No | — | LONGTEXT (DC2Type:array) |
| `payroll_reports` | `payroll_reports` | `array` | — | Yes | No | — | LONGTEXT (DC2Type:array) |
| `leave_policy` | `leave_policy` | `array` | — | Yes | No | — | LONGTEXT (DC2Type:array) |
| `emp_leaves` | `emp_leaves` | `array` | — | Yes | No | — | LONGTEXT (DC2Type:array) |
| `holiday_config` | `holiday_config` | `array` | — | Yes | No | — | LONGTEXT (DC2Type:array) |
| `leave_request` | `leave_request` | `array` | — | Yes | No | — | LONGTEXT (DC2Type:array) |
| `leave_calendar` | `leave_calendar` | `array` | — | Yes | No | — | LONGTEXT (DC2Type:array) |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `mainModules` | OneToOne | MainModules | inverse | — | — | — | persist, remove | false | mappedBy `submodule` |

### 3h. Notifications / Audit / Sync

#### `Notifications` → **`notifications`**

In-app notification fan-out row (one per recipient). Also triggers an email.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `action` | `action` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `description` | `description` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `datetime` | `datetime` | `datetime` | — | Yes | No | — | DATETIME. Set manually by the caller |
| `notification_type` | `notification_type` | `integer` | — | Yes | No | — | INT. Implicit enum 0–4, see §4 |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `recipient_department` | ManyToOne | Department | owning | `recipient_department_id` | NULL (implicit) | — | — | false | inversedBy `recipient_division` |
| `recipient_division` | ManyToOne | Division | owning | `recipient_division_id` | NULL (implicit) | — | — | false | inversedBy `notifications` |
| `recipient_employee_record` | ManyToOne | EmployeeRecords | owning | `recipient_employee_record_id` | NULL (implicit) | — | — | false | inversedBy `notifications` |
| `sender_employee_record` | ManyToOne | EmployeeRecords | owning | `sender_employee_record_id` | NULL (implicit) | — | — | false | inversedBy `sender_notifications` |

#### `AuditTrailLog` → **`audit_trail_log`**

Audit trail written by `App\Service\AuditLog`. **No controller references it directly.**

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `ip_address` | `ip_address` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `transactions` | `transactions` | `text` | — | Yes | No | — | LONGTEXT. `LONGTEXT` holding a JSON-encoded payload as a *string* (not a `json` column) |
| `datetime` | `datetime` | `datetime` | — | No | No | — | DATETIME. Carries a stray `#[ORM\JoinColumn(nullable:true)]` attribute on a **scalar** column — meaningless and ignored by Doctrine |

| Rel property | Kind | Target | Side | Join col | FK null | onDelete | cascade | orphanRem | Link |
|---|---|---|---|---|---|---|---|---|---|
| `user` | ManyToOne | User | owning | `user_id` | NULL (implicit) | — | — | false | inversedBy `auditTrailLogs` |

#### `SyncConnection` → **`sync_connection`**

Credentials for the external biometric MySQL database. **Password stored in plain text.**

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `username` | `username` | `string` | 255 | No | No | — | VARCHAR(255). Read by `SyncDatabaseConnection` as `$row['user']` — key mismatch, see §7.2 |
| `password` | `password` | `string` | 255 | No | No | — | VARCHAR(255). Plain-text DB password in a VARCHAR(255) column |
| `dbname` | `dbname` | `string` | 255 | No | No | — | VARCHAR(255) |
| `host` | `host` | `string` | 255 | No | No | — | VARCHAR(255) |

#### `Options` → **`options`**

Generic `option_name`/`option_value` key-value store. **Completely unreferenced** — see §6.

| Property | Column | Type | Len/Prec | Null | Uniq | Default | Notes (MySQL DDL) |
|---|---|---|---|---|---|---|---|
| `id` | `id` | `integer` | — | No | No | — | INT. PK, AUTO_INCREMENT |
| `option_name` | `option_name` | `string` | 255 | Yes | No | — | VARCHAR(255) |
| `option_value` | `option_value` | `json` | — | Yes | No | — | JSON |


---

## 4. Implicit enum catalogue

**There is not a single PHP `enum`, `BackedEnum`, MySQL `ENUM`, `CHECK` constraint or
lookup FK behind any of the values below.** Every one of them is a bare `INT`,
`SMALLINT` or `VARCHAR(255)` whose meaning lives only in controller `if` statements
and Twig `{% set %}` maps. A SQLAlchemy port should introduce real `Enum`/`IntEnum`
types — but must preserve the exact stored values shown here.

Evidence sources are cited per entry: `api:` = `/mnt/f/laragon/www/wchhris-api/src/…`,
`web:` = `/mnt/f/laragon/www/wchhris/templates/…`.

### 4.1 Approval-workflow statuses (0 / 1 / 2)

| Entity.column | Storage | 0 | 1 | 2 | Evidence |
|---|---|---|---|---|---|
| `LeaveRequest.status` | **`VARCHAR(255)`** (!) | `Pending` | `Approved` | `Rejected` | web:`leave_request/apps-leave-request.html.twig:57-61` `{% set holiday_status = {0:'Pending',1:'Approved',2:'Rejected'} %}`; api:`LeaveRequestController.php:191` `setStatus(0)` on create; `:337` `if ($data['status'] == "1")` (string compare) |
| `EmployeeOvertimeRequest.status` | `SMALLINT` | `Pending` | `Approved` | `Rejected` | web:`administration/overtime_request.html.twig:54-58` (identical map); api:`EmployeeOvertimeRequestController.php:97` `setStatus(0)`, `:227` `setStatus((int) $status)` |

Side-effect coupled to OT status (api:`EmployeeOvertimeRequestController.php:213-216`):
approving sets `WorkerLogs.overtime_approved = true`, any other outcome sets it `false`.

> ⚠️ `LeaveRequest.status` is a **string** column while `EmployeeOvertimeRequest.status`
> is a **smallint**, yet they carry the identical enum. Port both to the same IntEnum
> and cast on read for `leave_request`.

### 4.2 `AccountabilityRecords.status` — `INT`

| Value | Meaning |
|---|---|
| `0` | Assigned |
| `1` | Returned |
| `2` | Lost |

Evidence: web:`employee_profile/apps-employee-profile.html.twig:2940-2942`
(`{0:'Assigned',1:'Returned',2:'Lost'}`) and the three `<option value="0|1|2">`
blocks at lines 3797-3799 and 3844-3846. API stores it verbatim
(`AccountabilityRecordsController.php:75` `setStatus((int) $status)`); the API never
interprets the value.

### 4.3 `LeavePolicy` eligibility enums

**`LeavePolicy.gender` — stored as `VARCHAR(255)`, nullable, holding a numeric string**

| Value | Meaning |
|---|---|
| `"0"` | All |
| `"1"` | Male |
| `"2"` | Female |
| `"3"` | Other |

Evidence: web:`leave_policy/leave_policy.html.twig:165-170` (create form) and
`:269-274` (edit form, compared as `leave_policy.gender == "0"` — string comparison,
confirming string storage).

**`LeavePolicy.marital` — stored as `SMALLINT`, NOT NULL**

| Value | Meaning |
|---|---|
| `0` | All |
| `1` | Single |
| `2` | Married |
| `3` | Widowed |

Evidence: web:`leave_policy/leave_policy.html.twig:176-181` and `:280-285`
(compared as `leave_policy.marital == 0` — integer comparison).

> ⚠️ Two enums on the same table, semantically parallel, stored with **different
> column types** (`VARCHAR` vs `SMALLINT`) and compared with **different operand
> types** in Twig. Also note `marital` has no `3 = Other`/`4 = Separated`, while
> `EmployeeRecords.civil_status` (§4.4) *does* offer `Legally Separated` — so a
> "Legally Separated" employee matches **no** marital policy except `0 = All`.

**`LeavePolicy.type`** — nullable free-text. The input is **commented out** in both
the create and edit Twig forms (`{# … #}` around lines 159 and 263), so in practice
this column is always `NULL`. No enum.

### 4.4 `EmployeeRecords` demographic enums (all `VARCHAR(255)`, all NOT NULL)

**`civil_status`**

| Stored value |
|---|
| `Single` |
| `Married` |
| `Widowed` |
| `Legally Separated` |

Evidence: web:`employee_payroll_profile/employees-payroll-profile.html.twig:283-287`.
(The `manpower/apps-employees.html.twig` edit form populates the same `<select>`
dynamically, so the payroll-profile form is the canonical source of the option list.)

**`gender`**

| Stored value |
|---|
| `Male` |
| `Female` |

Evidence: web:`employee_payroll_profile/employees-payroll-profile.html.twig:275-276`
and `manpower/apps-employees.html.twig:282-283`.
Note this is a **different enum domain** from `LeavePolicy.gender` (numeric codes) and
from `User.gender` (free text) — three gender representations in one schema.

**`employee_status`**

| Stored value | Meaning |
|---|---|
| `Active` | Currently employed — the only value the backend ever filters on |
| `Terminated` | Separated for cause |
| `Resigned` | Voluntary separation |

Evidence: web:`manpower/apps-employees.html.twig:415-417`.
Backend hard-codes the literal `'Active'` in **9 places**:
api:`PayrollGenerationController.php:256`; `PayrollReportsController.php:238, 369, 638, 787, 920, 1062, 1229`;
`WorkerLogsRepository::findAllLogsForActiveEmployees()` (default arg is the lowercase
`'active'` — a **case-sensitivity bug** if the column collation is ever made binary);
plus `NotificationService.php` (4 × `findBy(['employee_status' => 'Active', …])`).

**`employment_type`** — free-text `<input type="text" id="employmentType">`
(web:`manpower/apps-employees.html.twig:404`). **No enum, no FK to `contract_types`.**

### 4.5 `SelectedEmployeeLeaves` enums (both `INT`, NOT NULL)

**`carry_over_policy`**

| Value | Meaning |
|---|---|
| `0` | Not Carried Over |
| `1` | Carried Over |
| `2` | Non Carried over but Cashble *(sic — "Cashable")* |
| `3` | Not Carried over and Cashble *(sic)* |

Evidence: web:`leave_policy/employee_leave.html.twig:273-277`.
Default on create: `0` (api:`EmployeeLeavesController.php:153, 214`).

**`status`** — ⚠️ **inverted polarity relative to every other status column**

| Value | Meaning |
|---|---|
| `0` | Enabled |
| `1` | Disabled |

Evidence: web:`leave_policy/employee_leave.html.twig:283-285`.
Default on create: `0` = Enabled (api:`EmployeeLeavesController.php:154, 215`).

### 4.6 `Notifications.notification_type` — `INT`, nullable

Set exclusively by `App\Service\NotificationService`; the value encodes the
**fan-out audience**, not the notification's subject.

| Value | Audience | Set by |
|---|---|---|
| `0` | `ALL` — active employees matching **both** division **and** department | `createNotification()` / `createNotificationUsingToken()` case `'ALL'`; also the `default:` fallback |
| `1` | `DEP_ONLY` — active employees in the department | case `'DEP_ONLY'` |
| `2` | `DIV_ONLY` — active employees in the division | case `'DIV_ONLY'` |
| `2` **or** `3` | `DIV_DEP` | ⚠️ **Inconsistent:** `createNotification()` assigns **`2`** (`NotificationService.php:60`) but `createNotificationUsingToken()` assigns **`3`** (`:110`) for the same `'DIV_DEP'` case |
| `"4"` | Single named recipient | `createNotificationForSpecificUser()` passes the **string** `"4"` (`NotificationService.php:137`) into an `?int` column — silently coerced to `4` |

The audience *string* keys accepted by the service are: `ALL`, `DEP_ONLY`,
`DIV_ONLY`, `DIV_DEP` (anything else falls through to `0`). Only **one** call site
exists in the whole API: `ManpowerController.php:2394` with `"DEP_ONLY"`.

### 4.7 `UserType.user_code` — role codes (`VARCHAR(255)`)

`user_code` is a free-text short code stored per role row; roles are **created at
runtime** through `POST /api/usertype/create` and `SuperAdminController`, so the set is
open-ended. The codes actually referenced in source are:

| Code | Meaning | Evidence |
|---|---|---|
| `SADM` | Super Admin | web:`src/Controller/HomeController.php:136` `$allowedUserTypes = ["SADM", "ADM", "HR"];`; `SuperAdminController.php:266` `invalidateSessionsByUserType('SADM')` (commented) |
| `ADM` | Administrator | web:`HomeController.php:136` |
| `HR` | Human Resources | web:`HomeController.php:136` |
| `SUR` | **Default role auto-assigned to every employee-derived `User`** | api:`ManpowerController.php:173` and `:271` — `findOneBy(['user_code' => "SUR"])` when creating a login for a newly added / bulk-imported employee |

Login returns `user_type_code` to the SPA (api:`LoginController.php:202, 315`), which
stores it in the session as `userTypeCode` (web:`HomeController.php:434`) and gates
page access with the `["SADM","ADM","HR"]` allow-list.

`UserType.removed` (`SMALLINT NOT NULL`) is a soft-delete flag: `0` = live,
non-zero = removed. It is written with a PHP **boolean** (`setRemoved(false)`) at
api:`LoginController.php:375`.

### 4.8 RBAC — `can_*` permission flags

The permission atom is a 4-key associative array, PHP-serialised into a
`Types::ARRAY` column:

```php
['can_view' => bool, 'can_add' => bool, 'can_edit' => bool, 'can_delete' => bool]
```

Exhaustive flag list (grep of `can_[a-z_]*` across API + templates returns exactly
these four, nothing more):

| Flag | `$access_type` argument |
|---|---|
| `can_view` | `'view'` |
| `can_add` | `'add'` |
| `can_edit` | `'edit'` |
| `can_delete` | `'delete'` |

Defaults on role creation are all `false`
(api:`SuperAdminController.php:117-120`). The whitelist
`['can_view','can_add','can_edit','can_delete']` is re-asserted at
`SuperAdminController.php:203, 261, 318, 360`.

Enforcement (`App\Service\UserAccessValidation::validateUserAccess($request, $submodule, $access_type)`)
resolves `UserType → MainModules → SubModules`, picks the submodule array via a
`switch`, then checks `!empty($access['can_' . $access_type])`.

**Submodule keys accepted by the `switch` (11):**

| Key | SubModules getter | Column |
|---|---|---|
| `subdivision` | `getSubdivision()` | `subdivision` |
| `division` | `getDivision()` | `division` |
| `department` | `getDepartment()` | `department` |
| `daily_time_record` | `getDailyTimeRecord()` | `daily_time_record` |
| `phase` | `getPhase()` | `phase` |
| `owner` | `getOwner()` | `owner` |
| `models` | `getModels()` | `models` |
| `model_types` | `getModelTypes()` | `model_types` |
| `emp_settings` | `getEmpSettings()` | `emp_settings` |
| `shifts` | `getShifts()` | `shifts` |
| `employee_projects` | `getEmployeeProjects()` | ⚠️ **NO SUCH GETTER / NO SUCH COLUMN** — see below |

> 🐞 **Two bugs in the RBAC switch.**
> 1. `case 'employee_projects'` calls `$sub_module_access->getEmployeeProjects()`,
>    which **does not exist** on `SubModules` (the real property is `emp_project`,
>    getter `getEmpProject()`). Any call with that key is a fatal `Error`. It is
>    never reached: grepping every `validateUserAccess(...)` call site yields only
>    `subdivision`, `division`, `department`, `phase`, `owner`, `models`,
>    `model_types`, `shifts` × {view, add, edit, delete} = 32 call sites.
> 2. `daily_time_record` is handled by the switch but **never called** by any controller.

**Full `SubModules` permission-column list (25 — the switch only covers 10 of them):**

`daily_time_record`, `subdivision`, `division`, `department`, `phase`, `owner`,
`models`, `model_types`, `emp_settings`, `shifts`, `projects`, `emp_project`,
`emp_list`, `sss_config`, `pagibig_config`, `bir_config`, `philhealth_config`,
`payroll`, `payroll_reports`, `leave_policy`, `emp_leaves`, `holiday_config`,
`leave_request`, `leave_calendar`.

All 25 are returned to the SPA on login (api:`LoginController.php:150-179`), so the
**frontend enforces 25 submodules while the backend can only enforce 10**.

**`MainModules` permission-column list (5):** `project`, `humanres`,
`administration`, `payroll`, `emp_leaves` (api:`LoginController.php:137-143`).

**`User.roles` (`json`)** is the Symfony-security role array
(`ROLE_USER`, …). It is **completely unused** by this application's authorisation —
`security.yaml` only requires `IS_AUTHENTICATED_FULLY` on `^/api`, and every real
check goes through `UserAccessValidation`. Two parallel, unrelated RBAC systems.

### 4.9 `AttendanceTypes.name` — DTR day classification (`VARCHAR(255)`)

A **user-editable lookup table** (`AttendanceController` exposes list/find/update but
**no create and no delete**), so the row set is data, not code. The names the backend
depends on by literal string are:

| Name | Where it is hard-coded |
|---|---|
| `Absent` | api:`CheckEmpDtrController.php:142, 161`; `ManpowerController.php:2495, 2516, 2541`; `SyncWorkerController.php:323` — all `findOneBy(['name' => 'Absent'])` |
| `Present` | web:`manpower/apps-manpower.html.twig:1031, 1038, 1167, 1240` — `attendance_status.name !== 'Absent'` / `=== 'Present'` |

Additional per-row behaviour flags on the same table:

| Column | Type | Meaning |
|---|---|---|
| `is_hours_rendered` | `TINYINT(1)` **NOT NULL** | Whether the type contributes rendered hours to payroll |
| `hours_provided` | `DOUBLE` NULL | Fixed hours credited for the type (e.g. paid leave) |
| `automated_attendance` | `TINYINT(1)` NULL | **Exactly one row is expected to be `true`**; it is the type auto-assigned during biometric sync (api:`ManpowerController.php:2370`, `SyncWorkerController.php:140` — `findOneBy(['automated_attendance' => true])`) |

A third literal, `Pending`, appears in the manpower UI's OT dropdown
(web:`apps-manpower.html.twig:1170, 1177, 1197, 1245, 1257`) but it is an
**OT-request status label (§4.1), not an attendance type**.

### 4.10 `ContractTypes` — `name` / `code` (`VARCHAR(255)`)

**No fixed value set exists.** `ContractTypesController` is a plain CRUD API
(`/api/contract-types/{list,create,find,update,delete}`) over a free-form
name+code+archived table. Crucially, **nothing joins to it** — `EmployeeRecords`
stores `employment_type` as free text (§4.4). See §6.

`ContractTypes.archived` is the schema's only **NOT NULL** archive flag; the
controller defaults it to `false` on create.

### 4.11 `Worker.status` and `WorkerLogs.type` (`VARCHAR(255)`, nullable)

Both are **verbatim pass-throughs from the external biometric MySQL database**, not
enums defined by this system:

* `Worker.status` ← `$row['status']` of `SELECT * FROM worker`
  (api:`SyncWorkerController.php:59, 75`).
* `WorkerLogs.type` ← `$row['type']` of `SELECT * FROM worker_logs`
  (api:`SyncWorkerController.php:103, 110, 275`, written at `:197, 219, 305`).

Neither value is ever read, compared or branched on anywhere in the API or the
frontend. **Treat as opaque free text on port**; the authoritative day classification
is `WorkerLogs.attendance_status_id → attendance_types` (§4.9).

### 4.12 `HolidayConfig` — there is **no** `type` column

`HolidayConfig` has exactly: `name`, `date`, `multiplier_regular`,
`multiplier_overtime`, `archived`. The Philippine holiday *type* (Regular vs Special
Non-Working) is **encoded implicitly in the two multipliers**, which are free-form
`DOUBLE` inputs in the UI (web:`holiday/apps-holiday.html.twig:201, 206, 244, 249` —
"Multiplier (Regular)" / "Multiplier (Overtime)"). Conventional PH values a user
would enter:

| Holiday kind (implied) | `multiplier_regular` | `multiplier_overtime` |
|---|---|---|
| Regular Holiday | `2.0` | `2.6` |
| Special Non-Working Day | `1.3` | `1.69` |

Nothing in the code validates or constrains these. If the port wants a real
`holiday_type` enum, it must be **derived from the multipliers or added new**.

### 4.13 Payroll frequency — **no column, hard-coded semi-monthly**

There is **no `frequency`/`period_type`/`cutoff_type` column on any payroll entity**
(`EmployeePayroll`, `EmployeePayrollProfile`, `PayrollGroups`,
`PayrollCalculationConfig` were all checked). The cadence is baked into
`PayrollGenerationController`:

* `$bi_weekly_salary = $basic_salary / 2;` (lines 134, 354, 565) — the monthly salary
  is always halved.
* Comments state the intent explicitly: *"Calculate Mandatory deductions semi
  monthly"* (154, 374, 585), *"Calculate Loans Deduction semi monthly"* (160, 591),
  *"Calculate tax deduction semi monthly"* (163, 594).
* `PayrollGroups` carries only `date_start` / `date_end` / `remarks` — the period is
  whatever range the user picks; there is no enum and **no status column** (payroll
  groups cannot be "draft"/"posted"/"locked").
* The only DB-stored payroll constant is `PayrollCalculationConfig.no_hours_per_week`
  (single row, fetched via `findOneBy([], ['id' => 'ASC'])` at
  `PayrollGenerationController.php:281`).

⇒ On port: **semi-monthly is an invariant, not data.** If multiple frequencies are
ever needed, a new column is required.

### 4.14 Other payroll-adjacent status columns

| Entity.column | Type | Semantics | Note |
|---|---|---|---|
| `EmployeePayroll` | — | **has no status column at all** | A payslip cannot be draft/approved/released/void. Existence == final. |
| `PayrollGroups` | — | **has no status column at all** | No cut-off locking |
| `CashAdvance.enabled` | `TINYINT(1)` NULL | active / inactive amortisation | `NULL` is ambiguous |
| `SSSLoans.enabled` | `TINYINT(1)` NULL | active / inactive amortisation | `NULL` is ambiguous |
| `PagibigLoans.enabled` | `TINYINT(1)` NULL | active / inactive amortisation | `NULL` is ambiguous |
| `EmpTask.approved` | `TINYINT(1)` NULL | timesheet approval | tri-state boolean used as a 3-value status |
| `EmpTask.is_adjusted` | `TINYINT(1)` NULL | manually corrected | |
| `EmployeeProjects.is_assigned` | `TINYINT(1)` NULL | assignment active | |
| `WorkerLogs.overtime_approved` | `TINYINT(1)` NULL | mirrors `EmployeeOvertimeRequest.status == 1` | derived/denormalised |
| `WorkerLogs.is_time_calculated` | `TINYINT(1)` **NOT NULL** | sync idempotency guard | the only NOT NULL boolean in the DTR domain |
| `User.status` | `INT` NULL | **undocumented and never read** | dead column |
| `User.removed` | `INT` **NOT NULL** | soft delete (`0` = live) | |
| `UserType.removed` | `SMALLINT` NOT NULL | soft delete (`0` = live) | |

### 4.15 Soft-delete flag conventions (three incompatible spellings)

| Spelling | Column | Type | Entities |
|---|---|---|---|
| `archived` | `archived` | `TINYINT(1)` NULL | EmployeeRecords, User, Project, Subdivision, Phase, Category, Owner, ModelTypes, Shifts, EmpTask, EmployeeProjects, HolidayConfig, YearlyHoliday (13) |
| `archived` (**NOT NULL**) | `archived` | `TINYINT(1)` NOT NULL | ContractTypes — the lone exception |
| `isArchived` | `is_archived` | `TINYINT(1)` NULL | Division, Department, SSSConfig |
| `removed` | `removed` | `INT` NOT NULL (User) / `SMALLINT` NOT NULL (UserType) | User, UserType |
| *(none)* | — | — | **40 of 58 tables have no soft delete at all**: all payroll (EmployeePayroll, EmployeePayrollProfile, PayrollGroups, SalaryAdjustment, TaxShield, …), all loans/CA and their histories, all leave (LeavePolicy, LeaveRequest, YearlyEmployeeLeave, SelectedEmployeeLeaves), Worker, WorkerLogs, AttendanceTypes, DTRAdjutments, EmployeeOvertimeRequest, AccountabilityRecords, Notifications, AuditTrailLog, Model, Lots, Blocks, EmployeeAttachments, EmployeeAdditionalRecords, AffiliatedCompany, ProjectType, SyncConnection, Options, MainModules, SubModules, all 4 gov-contribution configs except SSSConfig |

Canonical "not deleted" predicate used by repositories:
`archived IS NULL OR archived = false` — i.e. **`NULL` means live**. Three
repositories deviate and use `archived != true`
(`SubdivisionRepository::findByNotArchived`, `EmployeeProjectsRepository`) or
`archived = false` (`ProjectRepository::findByNotArchivedV2`,
`SubdivisionRepository::findByNotArchivedV2`), which **silently drop every row whose
flag is `NULL`** — see §7.

---

## 5. Custom repository methods

All 58 repositories extend `ServiceEntityRepository`. **34 of them are pure
boilerplate** — constructor only, plus the maker-bundle's commented-out
`findByExampleField()` / `findOneBySomeField()` stubs — and are *not* listed here.

The **24** repositories below contain genuine queries (58 methods total). Everything
is DQL via `createQueryBuilder()`; there is **no raw SQL, no native query, no stored
procedure** anywhere in `src/Repository`. Pagination uses
`Doctrine\ORM\Tools\Pagination\Paginator`.

### 5.1 Employee & HR

**`EmployeeRecordsRepository`** (9 methods — the busiest repository)

| Method | What it does |
|---|---|
| `findAllPaginated(int $page = 1, int $perPage = 10)` | Non-archived employees, offset-paginated, wrapped in `Paginator`. |
| `findBySearchPaginated(?string $search, int $page, int $perPage)` | Same + `LIKE %search%` on `first_name`, `last_name`, `employee_code`. ⚠️ Uses `andWhere(...)->orWhere(...)->orWhere(...)` **without parentheses**, so the `archived` predicate is ORed away — archived employees leak into search results. |
| `findBySearchPaginatedWithFilter(?string $search, int $page, int $perPage, array $filters)` | Adds `LEFT JOIN e.user u` + `addSelect('u')`, forces `e.user IS NOT NULL`, and filters on `u.is_active` from a `['active','not_active']` filter array (both present ⇒ no filter). Correctly parenthesises the search OR-group. |
| `countFilteredEmployees(?string $search, array $filter_status)` | `COUNT(e.id)` twin of the above, for pagination totals. |
| `findByNotArchived()` | `archived IS NULL OR archived = false`. |
| `countByNotArchived()` | `COUNT` of the above. |
| `findByCode($employeeCode)` | Single employee by the business key `employee_code` (`getOneOrNullResult`). Throws `NonUniqueResultException` if codes are duplicated — and nothing prevents duplicates (§7.1). |
| `countAllRows(?string $search = null)` | Count with the same un-parenthesised OR bug as `findBySearchPaginated`. (An older parenthesis-free version is left in the file as a block comment.) |
| `findEmployeesWithoutSpecificProject(int $projectId)` | Intended: employees not yet assigned to a given project. ⚠️ **Broken** — it builds a sub-`QueryBuilder` then does `setParameter('excludedIds', $subquery->getDQL())`, binding the **DQL string** as a parameter value instead of embedding a subquery. It also builds the subquery off `EmployeeRecords` and then calls `->from('App\Entity\EmployeeProjects', …)`, producing a cartesian FROM. |

**`DepartmentRepository`** — `findAllPaginated()` (unfiltered!), `findByNotArchived()`
(`isArchived IS NULL OR = false`), `countByNotArchived()`.

**`DivisionRepository`** — identical trio to `DepartmentRepository`
(`findAllPaginated()` also unfiltered, so archived divisions appear on paginated lists).

### 5.2 Payroll

**`EmployeePayrollRepository`**

| Method | What it does |
|---|---|
| `findByPayrollProfileAndDateRange(int $payrollProfileId, $dateFrom, $dateTo)` | Latest single payslip for a profile fully contained in `[dateFrom, dateTo]` (`date_start >= :from AND date_end <= :to`), `ORDER BY date_start DESC`, `LIMIT 1`. Params are pre-formatted `Y-m-d` strings. |
| `findByPayrollProfileAndDateRangeList(...)` | Same predicate, returns **all** matching payslips ordered `date_start DESC`. |

**`PayrollGroupsRepository`**

| Method | What it does |
|---|---|
| `findByDateRange($dateStart, $dateEnd)` | First cut-off group **overlapping** the given range (`p.date_start <= :dateEnd AND p.date_end >= :dateStart`), `LIMIT 1`. Note this is an *overlap* test, unlike `EmployeePayrollRepository`'s *containment* test. |
| `findByDateStartYear(int $year)` | All groups whose `date_start` falls in `$year-01-01 … $year-12-31 23:59:59`. |
| `findLatestPayrollGroup()` | Most recent group by `date_end DESC`, `LIMIT 1`. |

**`SSSConfigRepository`**

| Method | What it does |
|---|---|
| `findNotArchived()` | All non-archived SSS brackets (`isArchived IS NULL OR = false`), `ORDER BY id ASC`. |
| `findOneByIdAndNotArchived(int $id)` | Single non-archived bracket by id. |

### 5.3 Attendance / DTR

**`WorkerLogsRepository`** (9 methods)

| Method | What it does |
|---|---|
| `getLastWorkerLog()` | Newest log overall (`loginDate DESC`, `LIMIT 1`) — used as the sync high-water mark. |
| `countLogs()` | `COUNT(id)` of all logs (dashboard tile). |
| `countTodayLogs()` | `COUNT(id)` where `loginDate` ∈ `[today 00:00, tomorrow 00:00)`. |
| `findByUserAndLoginDate(int $userId, string $loginDate)` | Logs for a worker on a day, via `loginDate LIKE 'YYYY-MM-DD%'` (string prefix match on a DATETIME — unindexable). |
| `findByUserAndDateRange($workerId, $startDate, $endDate)` | Logs for one worker in a date range, `loginDate DESC`. |
| `findByDateRange($startDate, $endDate)` | All logs in range, `LEFT JOIN user→worker`, `LEFT JOIN worker.emp_record`, requiring `emp_record IS NOT NULL` (i.e. only biometric workers linked to a real employee). |
| `findByDateRangeWithWorkerId($startDate, $endDate, $workerId)` | Same, narrowed to one worker; drops the `emp_record` requirement. |
| `searchIfExisitingDate($startDate, int $workerId)` *(sic — typo in the method name)* | Idempotency probe used by the biometric sync: does a log already exist for this worker on this date? `loginDate LIKE 'YYYY-MM-DD%'`, `LIMIT 1`. |
| `findAllLogsForActiveEmployees(string $status = 'active', ?$dateFrom, ?$dateTo)` | `JOIN wl.user w JOIN w.emp_record er WHERE er.employee_status = :status`, optional date bounds, `ORDER BY w.id, wl.loginDate DESC`. ⚠️ Default arg is lowercase `'active'` but the stored value is `'Active'` (§4.4) — relies on a case-insensitive collation. |

**`WorkerRepository`**

| Method | What it does |
|---|---|
| `findAllWithEmpRecord()` | Workers linked to an employee: `emp_record IS NOT NULL AND emp_record != ''`. ⚠️ The second clause compares an **FK integer to an empty string**. |
| `findAllWithEmpRecordAndLogs()` | `LEFT JOIN` emp_record + workerLog, then `WHERE e IS NOT NULL AND l IS NOT NULL` — a LEFT JOIN immediately degraded to an INNER JOIN. |
| `findOneWithEmpRecordAndLogs(int $worker_id)` | Same, narrowed to one worker id. Returns an **array**, not a single object, despite the `findOne…` name. |

**`DTRAdjutmentsRepository`**

| Method | What it does |
|---|---|
| `findByEmpRecordAndDateRange(int $empRecordId, $dateStart, $dateEnd)` | Adjustment rows for one employee with `adjusted_date BETWEEN …`, `ORDER BY adjusted_date ASC`. |

**`ShiftsRepository`** — `findByNotArchived()`.

**`HolidayConfigRepository`** — `findNotArchived()` (`archived IS NULL OR = false`, `ORDER BY id ASC`).

**`YearlyHolidayRepository`** — `findNotArchived()` (same shape).

### 5.4 Projects / Manpower / Construction

**`ProjectRepository`** (7 methods)

| Method | What it does |
|---|---|
| `findOneByCodeOrName(string $code)` | Non-archived project by `code`. (Name says "OrName" but only `code` is used.) |
| `findAllPaginated($page, $perPage)` | Non-archived projects, `Paginator`. |
| `findNotArchivedWithRelations(int $limit = 50, int $offset = 0)` | The big eager-load: joins `subdivision → phases → blocks` and `categories → blocks / lots / model`, with `addSelect` on all 7 aliases, filtering archived at project/subdivision/phase level. ⚠️ Combining `setMaxResults` with fetch-joined collections makes Doctrine paginate in memory. |
| `findByNotArchived()` | `archived IS NULL OR = false`. |
| `findByNotArchivedV2()` | `getArrayResult()` projection using `PARTIAL`. ⚠️ **Broken field names**: `PARTIAL s.{… subdivisionCode …}` and `PARTIAL ph.{… totalBlocks, totalLots …}` — the actual properties are `subdivision_code`, `total_blocks`, `total_lots`. Also uses `p.archived = false`, which drops rows where `archived IS NULL`. |
| `countByNotArchived()` | `COUNT` of non-archived. |
| `findOneByNotArchived($id)` | Project by id with `employeeProjects → empTasks` joined. ⚠️ Operator-precedence bug: `where('e.archived IS NULL OR e.archived = false AND (emp_task.archived IS NULL)')` — `AND` binds tighter than `OR`, so the task filter only applies to the second branch. Returns an array. |

**`SubdivisionRepository`** (6 methods)

| Method | What it does |
|---|---|
| `findOneByCodeOrName(string $code, string $name)` | ⚠️ Same precedence bug: `where(code = :code)->orWhere(name = :name)->andWhere(archived IS NULL OR archived = false)`. |
| `findAllPaginated($page, $perPage)` | Non-archived, `Paginator`. |
| `findByCode($code)` | **All** subdivisions with a given `subdivision_code`, `ORDER BY id ASC` — proving the code is not unique. |
| `findByNotArchived()` | Uses `archived != :archived` with `true` ⇒ **drops rows where `archived IS NULL`** (SQL three-valued logic). Inconsistent with every other `findByNotArchived`. |
| `findByNotArchivedV2()` | Eager-loads `phases → blocks`; filters `s.archived = false` ⇒ same NULL-dropping problem. |
| `countByNotArchived()` | `archived IS NULL OR = false` — the *correct* predicate, so the count and the list disagree. |

**`PhaseRepository`**

| Method | What it does |
|---|---|
| `findOneByCodeOrName(string $code, string $name, int $subdivision_id)` | `(code = :code OR name = :name) AND subdivision = :id` — correctly parenthesised via `where(...)->andWhere(...)`. Duplicate-detection helper. |
| `findAllPaginated($page, $perPage)` | Non-archived, `Paginator`. |
| `findByNotArchived()` | `archived IS NULL OR = false`. |

**`BlocksRepository`**

| Method | What it does |
|---|---|
| `findBlockWithLotsWithoutCategory(int $blockId)` | Loads one block eager-joined to its lots and each lot's category, then keeps only lots with **no** category (`c.id IS NULL`) — i.e. the free/unsold lots of a block. |

**`CategoryRepository`** — `findOneByCodeOrName(string $code)` (by `code` only),
`findAllPaginated()`, `findByNotArchived()`.

**`ModelRepository`** — `findOneByCodeOrName(string $name)` (by `name` only);
`countByNotArchived()` ⚠️ which **counts every row** — the archive predicate was never
written, and `Model` has no `archived` column anyway.

**`ModelTypesRepository`** — `findByNotArchived()`.

**`OwnerRepository`** — `findByNotArchived()`, `countByNotArchived()`.

**`EmployeeProjectsRepository`**

| Method | What it does |
|---|---|
| `findByNotArchived()` | ⚠️ **Broken DQL** — `leftJoin('e.emp_record', 'emp_task')`. `EmployeeProjects` has **no `emp_record` association** (the property is `employee`), so this throws. The alias is also misleadingly named `emp_task`. Uses `archived != true`, dropping NULLs. |
| `countByNotArchived()` | Correct: `archived IS NULL OR = false`. |
| `findByNotArchivedDateRange()` | **Byte-identical to `findByNotArchived()`** — takes no date arguments and applies no date filter despite the name. Equally broken. |

**`EmpTaskRepository`**

| Method | What it does |
|---|---|
| `findByNotArchived()` | Non-archived tasks. |
| `findOneByNotArchived($emp_proj_id)` | Non-archived tasks for one `EmployeeProjects` row. Returns an **array** despite `findOne…`. |
| `findOneByNotArchivedWithDate($emp_proj_id, $startDate, $endDate)` | Same + `date BETWEEN`, `ORDER BY date ASC`. Also returns an array. |

### 5.5 Auth

**`UserRepository`**

| Method | What it does |
|---|---|
| `upgradePassword(PasswordAuthenticatedUserInterface $user, string $newHashedPassword)` | Symfony's `PasswordUpgraderInterface` hook — rehashes and flushes immediately. |
| `findOneByEmailOrUsernameOrPhone(string $identifier)` | `u.email = :id OR u.username = :id OR u.contactNum = :id`, `getOneOrNullResult()`. The **entire login path** (`LoginController`, `App\Security\UserProvider`, forgot-password). ⚠️ Throws `NonUniqueResultException` on any collision across the three columns, none of which is unique-constrained (§7.1). |

### 5.6 Repositories with **no** custom queries (34)

`AccountabilityRecordsRepository`, `AffiliatedCompanyRepository`,
`AttendanceTypesRepository`, `AuditTrailLogRepository`, `CashAdvanceHistoryRepository`,
`CashAdvanceRepository`, `ContractTypesRepository`,
`EmployeeAdditionalRecordsRepository`, `EmployeeAttachmentsRepository`,
`EmployeeOvertimeRequestRepository`, `EmployeePayrollProfileRepository`,
`LeavePolicyRepository`, `LeaveRequestRepository`, `LoanHistoryRepository`,
`LotsRepository`, `MainModulesRepository`, `NotificationsRepository`,
`OptionsRepository`, `PagibigConfigRepository`, `PagibigLoansHistoryRepository`,
`PagibigLoansRepository`, `PayrollCalculationConfigRepository`,
`PhilHealthConfigRepository`, `ProjectTypeRepository`, `SSSLoansHistoryRepository`,
`SSSLoansRepository`, `SalaryAdjustmentRepository`,
`SelectedEmployeeLeavesRepository`, `SubModulesRepository`,
`SyncConnectionRepository`, `TaxConfigRepository`, `TaxShieldRepository`,
`ThirteenthMonthPayConfigRepository`, `UserTypeRepository`,
`YearlyEmployeeLeaveRepository`.

These are accessed through `$em->getRepository(X::class)->find/findOneBy/findBy/findAll`
directly in controllers. **On port, none of them needs a bespoke data-access class.**

---

## 6. Dead / unused entities

Method: counted `\bClassName\b` occurrences across `src/Controller/**` (42 files),
across `src/Service` + `src/Security` (non-repository code), and across the other 57
entity files. A repository file always self-references its entity ~6 times, so
`other_src = 6` means "referenced by nothing but its own repository".

### 6.1 Fully dead — 0 controller references, no runtime reachability

| Entity | Table | Ctrl refs | Non-repo src refs | Entity refs | Verdict |
|---|---|---|---|---|---|
| **`Options`** | `options` | **0** | **0** | **0** | **Completely orphaned.** Nothing imports `App\Entity\Options` except `OptionsRepository`. The two grep hits for the *word* "Options" in `ModelControllersController.php` and `ProjectController.php` are `isAdditionalOptions()` / `setAdditionalOptions()` on **`ModelTypes`** — unrelated. Generic key/value store, never wired up. **Drop.** |
| **`ProjectType`** | `project_type` | **0** | **0** | 3 (all in `Project.php`) | **Orphaned lookup.** `Project.project_type_id` FK exists, but no controller ever sets it, reads it, or lists project types. There is no `ProjectTypeController` and no route. Rows can only ever be `NULL`. **Drop, or finish the feature.** |
| **`ThirteenthMonthPayConfig`** | `thirteenth_month_pay_config` | **0** | **0** | 3 (all in `EmployeePayrollProfile.php`) | **Superseded.** Its three booleans (`include_salary_adjustment`, `include_salary`, `include_tax_shield_pay`) were re-implemented as inline columns on `EmployeePayrollProfile` (`include_salary_adjustment_for_thirteenth_month`, `include_salary_for_thirteenth_month`, `include_taxshield__for_thirteenth_month`). The OneToOne is never populated. **Drop.** |
| **`AuditTrailLog`** | `audit_trail_log` | **0** | 4 (`Service/AuditLog.php`, `Service/NotificationService.php`, `Service/UserAccessValidation.php`, `Entity/User.php`) | 5 | **Not dead** — written indirectly by `App\Service\AuditLog::addAuditLog()`, which controllers call. Listed here only because a naive controller grep reports 0. **Keep.** (Note: `NotificationService` and `UserAccessValidation` merely `use` the class without using it — dead imports.) |

### 6.2 Near-dead / write-only / unreachable-feature entities

| Entity | Table | Ctrl refs | Status |
|---|---|---|---|
| `ContractTypes` | `contract_types` | 2 (its own controller's `use` + `new`) | **Feature island.** Full CRUD API at `/api/contract-types/*`, but **`entity_refs = 0`** — no other entity or controller joins to it. `EmployeeRecords.employment_type` is free text (§4.4, §4.10). Data can be entered and never used. |
| `PayrollCalculationConfig` | `payroll_calculation_config` | 2 | Single-row config read once (`PayrollGenerationController.php:281`). No CRUD endpoint exists — the row must be inserted by hand. `entity_refs = 0`. |
| `SyncConnection` | `sync_connection` | 5 | Read by `SyncWorkerController` / `CheckEmpDtrController` / `SuperAdminController` to build a raw PDO connection. `entity_refs = 0`. Also read by `App\Service\SyncDatabaseConnection`, which is **itself dead** — autowired by the `App\` resource glob but never injected anywhere (and it reads `$row['user']` for a column actually named `username`, §7.2). |
| `AccountabilityRecords` | `accountability_records` | 2 | Live but thin: only `AccountabilityRecordsController`. Its inverse side on `EmployeeRecords` is **broken** (§7.2), so `$employee->getAccountabilityRecords()` cannot be used. |
| `EmployeeOvertimeRequest` | `employee_overtime_request` | 2 | Live, single controller. |
| `LeaveRequest` | `leave_request` | 2 | Live, single controller (`LeaveRequestController`) + `EmployeeLeavesController` via its repository. |
| `PagibigLoansHistory` / `SSSLoansHistory` | `pagibig_loans_history` / `sssloans_history` | 2 each | Written by `PagibigController` / `SSSController` during payroll generation; never queried back except through the parent collection. |
| `Options` sibling check — `Category.block`, `Category.lot` | — | — | Not entities, but **dead columns**; see §7.7. |

### 6.3 Entities with no dedicated controller (reached only via a parent)

These are alive but have **no** controller of their own — they are always manipulated
through a related aggregate. Relevant when deciding which SQLAlchemy models need
their own service layer:

`Blocks`*, `Lots`, `Category`*, `Model`*, `Owner`*, `EmpTask`, `MainModules`,
`SubModules`, `AttendanceTypes`†, `CashAdvanceHistory`, `LoanHistory`,
`SSSLoansHistory`, `PagibigLoansHistory`, `TaxConfig`, `PayrollCalculationConfig`,
`AffiliatedCompany`†, `YearlyEmployeeLeave`, `SalaryAdjustment`†, `ProjectType`,
`Options`, `ThirteenthMonthPayConfig`, `AuditTrailLog`, `SyncConnection`.

\* handled by `ProjectController` / `BlocksController` / `ModelControllersController`.
† has a controller but no create/delete verbs (`AttendanceController` is
list/find/update only).

### 6.4 Orphan summary for the port

**Do not migrate (3 tables, 0 rows of business value):**
`options`, `project_type`, `thirteenth_month_pay_config`.

**Migrate but flag for product decision (3):**
`contract_types` (unused lookup), `payroll_calculation_config` (hand-seeded
single row), `sync_connection` (plain-text credentials — move to env/secrets).

**Dead code to drop alongside:** `App\Service\SyncDatabaseConnection`,
`ProjectTypeRepository`, `OptionsRepository`, `ThirteenthMonthPayConfigRepository`,
the `Project.project_type` association, the `EmployeePayrollProfile.thirteenthMonthPayConfig`
association, and the unused `AuditTrailLog` imports in `NotificationService` /
`UserAccessValidation`.
