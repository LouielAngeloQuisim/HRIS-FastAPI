# WCH HRIS API — Auth, RBAC, Employee Core, Org Structure & Misc

**Target:** `/mnt/f/laragon/www/wchhris-api` (Symfony 7 / PHP, Doctrine ORM, Lexik JWT)
**Scope:** Authentication, authorization (RBAC), EmployeeRecords master, org structure,
notifications, audit, dashboard, and cross-cutting weak spots.
**Mode:** READ-ONLY static analysis. Every claim below is traceable to a file:line.

---

## 0. Orientation

| Item | Value |
|---|---|
| Framework | Symfony (attribute routing, `config/routes.yaml` → `src/Controller/`) |
| ORM | Doctrine, attribute mapping, `src/Entity` (60 entities) |
| Auth | `lexik/jwt-authentication-bundle` (RS256 keypair) |
| Bundles | Framework, Maker, Doctrine, DoctrineMigrations, Security, **LexikJWT**, **JoseFramework**, **KnpPaginator**, **NelmioCors** |
| Controllers | 45 files in `src/Controller/` |
| **Total routes** | **280** `#[Route]` attributes |
| **RBAC-checked routes** | **38** (`validateUserAccess` calls) — **~13.6%** |
| Services | 6 in `src/Service/` + 1 in `src/Security/` |
| Migrations | **only 4** (`Version20250213092844` → `Version20250506061501`) — schema is NOT migration-managed |
| Fixtures | **none** (no `DataFixtures` dir, no seeds in repo) |

### Controllers requested vs. reality

| Requested | Status |
|---|---|
| `LoginController.php` | ✅ exists (22.8 KB) |
| `UsersController.php` | ✅ exists (11.2 KB) |
| UserType controller | ⚠️ **no dedicated controller.** UserType CRUD is split across `LoginController`, `UsersController`, `SuperAdminController` (see §G) |
| `SuperAdminController.php` | ✅ exists (22.8 KB) |
| `PermissionController.php` | ⚠️ exists but is an **empty MakerBundle stub** (43 lines, 1 route returning "Welcome to your new controller!") |
| `EmployeeRecordsController.php` | ✅ exists (19.9 KB) |
| **`DepartmentController.php`** | ❌ **DOES NOT EXIST** — Department CRUD lives in `ManpowerController` |
| **`DivisionController.php`** | ❌ **DOES NOT EXIST** — Division CRUD lives in `ManpowerController` |
| `ManpowerController.php` | ✅ exists — **125 KB, the largest file in the codebase** |
| `ProjectController.php` | ✅ exists — **120 KB**, 2nd largest |
| `BlocksController.php` | ✅ exists (3.7 KB, read-only) |
| `NotificationsController.php` | ✅ exists (8.1 KB) |
| `DashboardController.php` | ✅ exists (3.9 KB) |
| **AuditTrailLog controller** | ❌ **DOES NOT EXIST.** `AuditTrailLog` is a write-only entity — nothing in the API ever reads it back (see §E) |

---

## A. AUTHENTICATION FLOW

### A.1 Firewalls — `config/packages/security.yaml`

```yaml
providers:
    app_user_provider:   { entity: { class: App\Entity\User, property: email } }
    user_provider:       { id: App\Security\UserProvider }

firewalls:
    dev:   { pattern: ^/(_(profiler|wdt)|css|images|js)/, security: false }
    login:
        pattern: ^/api/login
        stateless: true
        json_login:
            check_path: /api/login
            username_path: identifier
            password_path: password
            provider: user_provider
    api:
        pattern: ^/api
        stateless: true
        jwt: ~
        provider: user_provider
    main:
        lazy: true
        provider: app_user_provider
```

**Two providers are configured and both are live.** `app_user_provider` (email only) backs
the `main` firewall; `user_provider` (email OR username OR contact_no) backs `login` + `api`.

### A.2 Access control

```yaml
access_control:
    - { path: ^/api/login,                roles: PUBLIC_ACCESS }
    - { path: ^/api/forget_password,      roles: PUBLIC_ACCESS }
    - { path: ^/api/validate_reset_token, roles: PUBLIC_ACCESS }
    - { path: ^/api/reset_password,       roles: PUBLIC_ACCESS }
    - { path: ^/api,                      roles: IS_AUTHENTICATED_FULLY }
```

> 🔴 **The access-control list is prefix-anchored on `^/api` only.**
> Any route **not** starting with `/api` falls through to the `main` firewall, which is
> `lazy: true` with **no authenticator configured** → effectively **anonymous / public**.
> `LoginController::signup()` is registered at **`/signup`** (no `/api` prefix). See §H-1.

### A.3 Login endpoint

`LoginController::login()` — `src/Controller/LoginController.php:92-211`

- **Route:** `POST /api/login` (name `api_login`)
- **Body:** `{ "identifier": "<email|username|contact_num>", "password": "<plain>" }`
- **Resolution:** `UserRepository::findOneByEmailOrUsernameOrPhone()` (`UserRepository.php:36-43`)
  — DQL `u.email = :identifier OR u.username = :identifier OR u.contactNum = :identifier`, properly parameterised.

Flow:
1. `400` if `identifier` or `password` missing.
2. `401 {"error1": "Invalid credentials 12 user not found."}` if no user.
3. `401 {"error2": "Invalid credentials 11 wrong password."}` if `isPasswordValid()` fails.
4. `401 {"error": "User is disabled."}` if `!$user->isActive()`.
5. `$token = $this->jwtManager->create($user)`.
6. Loads `UserType → MainModules → SubModules` and flattens the whole permission tree into the response.
7. `AuditLog::addAuditLog($request, json_encode($user), 'api/login', 'User Login')`.

> 🔴 **Username enumeration + oracle.** Steps 2 and 3 return *different* JSON keys
> (`error1` vs `error2`) with *different* messages ("user not found" vs "wrong password").
> An attacker can enumerate valid accounts with a single request each. The numbered
> debug strings ("credentials 12", "credentials 11") are leftover developer markers.

> 🔴 **`json_encode($user)` is written into the audit trail on every login.** `User` has no
> `JsonSerializable`, so this serialises **public properties only** — which includes
> `public ?bool $is_active` (`User.php:219`). Harmless today, but one visibility change
> away from persisting the password hash into `audit_trail_log`.

**Success response (200):**
```json
{ "message":"Login successful.", "token":"<JWT>", "user_id":1, "username":"<email>",
  "user_type_code":"...", "user_type_name":"...", "first_name":"", "last_name":"",
  "empCode":"", "main_module":{...}, "sub_module":{...}, "profile_image":"" }
```

The `main_module` / `sub_module` blobs are the **client-side permission map** the frontend
uses to show/hide nav items (see §B.5).

### A.4 Token format & lifetime — `config/packages/lexik_jwt_authentication.yaml`

```yaml
lexik_jwt_authentication:
    secret_key:  '%env(resolve:JWT_SECRET_KEY)%'
    public_key:  '%env(resolve:JWT_PUBLIC_KEY)%'
    pass_phrase: '%env(JWT_PASSPHRASE)%'
    token_ttl:   86400   # 24 hours (default is 3600)
```

- **Algorithm:** RS256 (asymmetric keypair; Lexik default).
- **TTL: 86400 s = 24 hours** — 24× the Lexik default. Long-lived bearer tokens.
- **Claims:** default Lexik payload built from `getUserIdentifier()` → `username` claim = the user's **email** (`User.php:414-417` returns `(string) $this->email`).

> 🔴 **Key paths and passphrase are committed in `.env`:**
> ```
> JWT_SECRET_KEY=F:/xampp/htdocs/Techrustrom/jwt/private.pem
> JWT_PUBLIC_KEY=F:/xampp/htdocs/Techrustrom/jwt/public.pem
> JWT_PASSPHRASE=fe5ddc1079d60b7c9c5f18acdda2c8be9a03a833e826bbcf6b1dbbcf1e09188e
> ```
> The **private-key passphrase is in version control**. The paths are absolute
> **Windows XAMPP** paths (`F:/xampp/...`) that point *outside* the project — and the
> project itself now lives under **Laragon** (`F:/laragon/www/...`), so these paths are
> stale. The commented-out portable form (`%kernel.project_dir%/config/jwt/*.pem`) was
> abandoned. Anyone with repo access + the key files can mint tokens for any user.

### A.5 JWT decode hook — `src/Service/JWTDecodedListener.php`

```php
public function onJWTDecoded(JWTDecodedEvent $event)
{
    $payload = $event->getPayload();
    if (!isset($payload['username']) && !isset($payload['email']) && !isset($payload['contact_no'])) {
        $event->markAsInvalid();
    }
}
```

Wired in `config/services.yaml` via tag
`{ name: 'kernel.event_listener', event: 'lexik_jwt_authentication.on_jwt_decoded', method: 'onJWTDecoded' }`.

Its **only** job is to assert at least one identifier claim exists. It does **not** check
IP binding, token revocation, `is_active`, or issued-at freshness.

> 🟠 **`email` and `contact_no` claims are never actually issued.** Lexik emits `username`.
> The two extra branches are dead conditions. Consequence: a token is accepted whenever
> `username` is present — which is always.

> 🔴 **No revocation / no denylist.** Because the firewall is `stateless: true` and there is
> no token store, **deactivating a user (`is_active = false`) does not invalidate their
> existing JWT.** A disabled or terminated employee keeps full API access for up to 24 h.
> `isActive()` is checked **only** at `/api/login` (line 119) and `/api/revalidate-session`
> (line 232) — never on subsequent authenticated requests.

### A.6 Subsequent request authentication

Standard Lexik: `Authorization: Bearer <JWT>` header. The `api` firewall (`pattern: ^/api`,
`jwt: ~`) extracts and verifies it; `UserProvider::loadUserByIdentifier()` re-hydrates the
`User` from the `username` claim on **every** request (a DB round-trip per call, no cache).

CORS — `config/packages/nelmio_cors.yaml`:
```yaml
allow_origin:  ['%env(CORS_ALLOW_ORIGIN)%']   # origin_regex: true
allow_methods: ['GET','OPTIONS','POST','PUT','PATCH','DELETE']
allow_headers: ['Content-Type','Authorization']
```
`.env`: `CORS_ALLOW_ORIGIN='^https?://(localhost|127\.0\.0\.1|example\.com|wchhris\.techrostrum\.com)(:[0-9]+)?$'`

> 🟠 The regex permits **plain `http://`** for the production host and whitelists
> `example.com` (placeholder left in). Tokens can traverse cleartext HTTP.

### A.7 Session re-validation (pseudo-refresh)

`LoginController::revalidateSession()` — `LoginController.php:213-324`

- **Route:** `POST /api/revalidate-session`
- **Body:** `{ "user_id": <int> }`
- Loads user by **primary key**, checks `isActive()`, then **mints a brand-new JWT** and
  returns the identical payload shape as `/api/login`.

> 🔴🔴 **CRITICAL — this is a horizontal + vertical privilege-escalation primitive.**
> The handler **never** compares `$user_id` against the authenticated principal. Any
> authenticated user can `POST {"user_id": 1}` and receive **a valid 24-hour JWT for
> user #1** (typically the super-admin). This is a complete account-takeover of every
> account in the system, reachable by any logged-in employee.
> *There is no password check, no ownership check, no role check.*
> It is nominally behind `^/api → IS_AUTHENTICATED_FULLY`, so it requires *any* valid
> token — the lowest possible bar.

> 🟠 Also mislabels its audit entry as `'api/login'` / `'User Login'` (line 295), so
> impersonation events are indistinguishable from genuine logins in the audit trail.

### A.8 Logout

> 🔴 **There is no logout endpoint.** No `/api/logout` route exists in any controller, and
> no `logout:` key is configured on any firewall. Combined with §A.5 (no revocation) and
> the 24-hour TTL, "logging out" can only be a client-side token discard. A stolen token
> remains valid for its full lifetime.

### A.9 Password hashing

`config/packages/security.yaml`:
```yaml
password_hashers:
    Symfony\Component\Security\Core\User\PasswordAuthenticatedUserInterface: 'auto'
```

- `'auto'` → Symfony picks the strongest available (bcrypt, or Argon2id if `sodium` present).
- `User implements PasswordAuthenticatedUserInterface` (`User.php:16`) with
  `#[ORM\Column] private ?string $password` (`User.php:37-38`).
- `UserRepository implements PasswordUpgraderInterface` with a working `upgradePassword()`
  (`UserRepository.php:25-34`) → transparent rehash-on-login is supported.
- Hashing sites: `LoginController::signup()` L348, `LoginController::resetPassword()` L493,
  and `UsersController::updateUser()`.
- `eraseCredentials()` is a **no-op** (`User.php:461-464`) — acceptable, since no
  `plainPassword` field is stored.

> 🟠 **No password policy anywhere.** No minimum length, complexity, history, rotation,
> or breach check on signup, update, or reset. `resetPassword()` only rejects an
> empty string (L481).

> 🟠 **No rate limiting / lockout.** `symfony/rate-limiter` is not in `bundles.php`, and
> `login_throttling` is not configured on the `login` firewall. Unlimited credential
> stuffing against `/api/login`. A `loginCount` column exists (`User.php:179-180`,
> default `0`) but is **never incremented** — dead field.

### A.10 "Remember me" / 2FA

> **Neither exists.** No `remember_me:` key in `security.yaml`; no
> `scheb/2fa-*` or any MFA package in `bundles.php`/`composer.json`. Single-factor only.
> The `biometricData` column on `User` (`User.php:86-87`, `varchar(999)`) relates to the
> **biometric time-clock device sync** (see §H), *not* to authentication.

### A.11 Password reset flow

Three public endpoints in `LoginController`:

| # | Route | Method | Lines |
|---|---|---|---|
| 1 | `/api/forget_password` | POST | 381-426 |
| 2 | `/api/validate_reset_token` | POST | 428-463 |
| 3 | `/api/reset_password` | POST | 465-502 |

**1. `forgetPassword()`** — body `{ "email": "..." }` (actually accepts email *or* username
*or* phone, since it reuses `findOneByEmailOrUsernameOrPhone`).
Generates the reset token via **`$this->jwtManager->create($user)`** (L408) — i.e. the reset
token *is a fully-valid authentication JWT*. Stores it in `user.reset_token`
(`varchar(1000)`, `User.php:221-222`) with `token_expiry = now + 24 hours` Asia/Manila.

```php
return $this->json(['message' => 'Password reset successful', 'email' => $email,
                    'employee' => $employeeArray, 'token' => $token], 200);
```

> 🔴🔴 **CRITICAL — the reset token is returned in the HTTP response body of an
> unauthenticated, public endpoint.** No email is ever sent (the `mailer` is configured but
> **`MailerInterface` is not injected into `LoginController` at all**). Therefore:
> **anyone who knows any employee's email address can POST to `/api/forget_password`,
> read the token straight out of the JSON, and immediately reset that account's password
> via `/api/reset_password`.** This is unauthenticated, remote, full account takeover of
> **any** account including super-admin. It requires no token, no session, nothing.

> 🔴 **Worse: the returned token is a real Lexik JWT.** The attacker doesn't even need
> step 3 — they can use the value directly as `Authorization: Bearer <token>` and are
> authenticated as the victim for 24 hours, because `JWTDecodedListener` only checks that
> a `username` claim exists and nothing marks the token as "reset-scoped".

> 🔴 **It also leaks PII.** The response embeds the victim's fully-serialised
> `EmployeeRecords` (`groups: 'employee'`, L419-425) — name, birthdate, address, contact,
> government IDs — to an unauthenticated caller.

> 🟠 Returns `401 {"error":"Invalid credentials 6."}` when the email is unknown →
> a second, unauthenticated **account-enumeration oracle**.

> 🟠 The response message is `'Password reset successful'` even though nothing was reset yet.

**2. `validateResetToken()`** — body `{ "token": "..." }`. Looks up
`findOneBy(['reset_token' => $token])`, compares `now <= token_expiry` (Asia/Manila),
returns `{"status": "Valid"|"Expired"}`.

> 🟠 When **no user matches**, it returns HTTP **200** with
> `{"message":"Token Validation Passed","status":"Expired"}` (L448-450). "Validation
> Passed" for a nonexistent token is contradictory, and the 200 masks the failure.

**3. `resetPassword()`** — body `{ "password": "...", "token": "..." }`.

```php
$pasword = $data['password'];   // [sic] typo, and unguarded array access
$token   = $data['token'];
```

> 🔴 **`token_expiry` is NEVER checked in `resetPassword()`.** It only does
> `findOneBy(['reset_token' => $token])` (L487) and, on a hit, rewrites the password.
> `validateResetToken` is a purely **advisory client-side call** — the enforcing endpoint
> ignores expiry entirely. **Reset tokens are therefore valid forever** until consumed.

> 🟠 Lines 470-471 read `$data['password']` / `$data['token']` **before** the
> `json_last_error()` check on L473 → PHP warning / `TypeError` on malformed or non-JSON
> bodies. The null-guards on L477-483 are unreachable for the missing-key case.

> ✅ Does correctly null out `reset_token` and `token_expiry` after use (L495-496), so the
> token is single-use.

> 🟠 **No audit log** on `resetPassword()` — the one place it matters most. The
> `forgetPassword` audit call is **commented out** (L423).

### A.12 Signup

`LoginController::signup()` — `LoginController.php:327-359`

```php
#[Route('/signup', name: 'api_signup', methods:['POST','GET'])]
```

> 🔴🔴 **CRITICAL — unauthenticated public user creation with caller-chosen role.**
> 1. The path is **`/signup`**, *not* `/api/signup`. It therefore **does not match any
>    `access_control` rule** and is handled by the `main` firewall, which has **no
>    authenticator** → **fully anonymous**.
> 2. The body's `role` field is looked up directly:
>    `$userTypeRepository->findOneBy(['user_code' => $role])` (L346) and assigned with
>    **no validation whatsoever** — the caller picks their own privilege level.
> 3. `$user->setActive(true)` (L342) — the account is live immediately.
>
> **A single anonymous `POST /signup` with the super-admin `user_code` yields a working
> super-admin account.**
>
> 4. It also accepts **`GET`** (`methods:['POST','GET']`), so the attack is a
>    state-changing operation reachable by URL — trivially CSRF-able and cacheable.
> 5. `$user->setUserId('test')` — a **hardcoded literal** written to every created row.
> 6. No uniqueness check on email/username → duplicate accounts; and since
>    `findOneByEmailOrUsernameOrPhone` uses `getOneOrNullResult()`, a duplicate email
>    later throws `NonUniqueResultException` and **breaks login for that identifier**
>    (a persistent DoS).
> 7. No `$userType` null-check → assigning `null` on a bad role silently creates a
>    role-less user.
> 8. No audit log.

### A.13 Auth summary matrix

| Concern | State |
|---|---|
| Login | ✅ `POST /api/login`, `identifier` + `password` |
| Token | Lexik JWT, RS256, **24 h TTL** |
| Refresh | ⚠️ none — `revalidate-session` is a **broken impersonation endpoint** |
| Logout | ❌ **does not exist** |
| Revocation | ❌ none; disabling a user does not kill live tokens |
| Password hashing | ✅ `auto` (bcrypt/Argon2id) + rehash-on-login supported |
| Password policy | ❌ none |
| Rate limiting / lockout | ❌ none |
| Remember me | ❌ none |
| 2FA / MFA | ❌ none |
| Password reset | 🔴 **token returned in public response body; expiry never enforced** |
| Signup | 🔴 **public, anonymous, self-assigned role, GET-able** |
| Account enumeration | 🔴 via `/api/login` and `/api/forget_password` |

---

## B. RBAC — ROLE & PERMISSION MODEL

### B.1 The chain

```
User ──ManyToOne──> UserType ──OneToOne──> MainModules ──OneToOne──> SubModules
 │                    │                        │                        │
 │                    ├─ name (string)         ├─ project      : array  ├─ 24 × array
 │                    ├─ user_code (string)    ├─ humanres     : array  │  each = {can_view,
 │                    └─ removed  (smallint)   ├─ administration:array  │   can_add, can_edit,
 └─ roles : json (Symfony) — ALWAYS EMPTY      ├─ payroll      : array  │   can_delete}
                                               └─ emp_leaves   : array
```

| Mapping | Declaration |
|---|---|
| `User.user_type` | `#[ORM\ManyToOne(inversedBy: 'users')] private ?UserType $user_type` — `User.php:182-185` |
| `UserType.users` | `#[ORM\OneToMany(targetEntity: User::class, mappedBy: 'user_type')]` — `UserType.php:35-36` |
| `UserType.main_module` | `#[ORM\OneToOne(inversedBy: 'userType', cascade:['persist','remove'])]` — `UserType.php:38-40` |
| `MainModules.submodule` | `#[ORM\OneToOne(inversedBy:'mainModules', cascade:['persist','remove'])]` — `MainModules.php:31-33` |

**One `UserType` ⇄ one `MainModules` ⇄ one `SubModules`.** Permissions are *not* a join table —
they are **serialised PHP arrays stored in columns on a single row per role**.

### B.2 Symfony's native RBAC is entirely unused

```php
// src/Entity/User.php:424-431
public function getRoles(): array
{
    $roles = $this->roles;
    $roles[] = 'ROLE_USER';       // guarantee every user at least has ROLE_USER
    return array_unique($roles);
}
```

> 🔴 **The `roles` column is never written to.** Repo-wide search finds `ROLE_` **only**
> inside `User::getRoles()` itself. There is **not a single** `isGranted()`,
> `#[IsGranted]`, `denyAccessUnlessGranted()`, Voter, or `@Security` annotation
> anywhere in `src/`.
> **Therefore every authenticated user — from janitor to super-admin — carries exactly
> the identical Symfony role set: `['ROLE_USER']`.** The `access_control` rule
> `^/api → IS_AUTHENTICATED_FULLY` is the *only* framework-level gate, and it is
> satisfied by any valid token. All differentiation depends on controllers voluntarily
> calling `UserAccessValidation`.

### B.3 The permission flags — exact names

Canonical definition, `SuperAdminController::createUserType()` L114-119 and
`MainModules::setPermissions()` / `SubModules::setPermissions()`:

```php
$defaultPermissions = [
    'can_view'   => false,
    'can_add'    => false,
    'can_edit'   => false,
    'can_delete' => false,
];
```

Validated on write against the whitelist `['can_view','can_add','can_edit','can_delete']`
(`SuperAdminController.php` L200, L266, L318, L358) with a strict `is_bool()` type check.
**Default is deny-all** — a newly created UserType has every flag `false`. ✅ Good default.

`UserAccessValidation` reconstructs the key as `'can_' . $access_type` (L98), so callers
pass the bare verb: `'view'`, `'add'`, `'edit'`, `'delete'`.

> ⚠️ **There is no `route` or `key` field.** The submodule identity is a **magic string**
> matched by a hand-written `switch` in `UserAccessValidation` (L54-95) against a
> **hard-coded property name** on `SubModules`. Adding a module means editing the entity,
> the switch, `setPermissions()`, both `LoginController` payload builders, and
> `SuperAdminController`'s validation array — 5+ places, no single source of truth.

### B.4 MainModules — the 5 top-level modules

| Property | Type | Meaning |
|---|---|---|
| `project` | `Types::ARRAY` | Project / construction module |
| `humanres` | `Types::ARRAY` | Human Resources |
| `administration` | `Types::ARRAY` | Administration / settings |
| `payroll` | `Types::ARRAY` | Payroll |
| `emp_leaves` | `Types::ARRAY` | Employee leaves |

> 🟠 `MainModules` permissions are **returned to the client at login but never enforced
> server-side.** `UserAccessValidation` reads `getMainModule()` only to confirm it is
> non-null (L40-47) — it never inspects `project`/`humanres`/etc. flags. Main-module
> permissions are **pure frontend menu decoration**.

### B.5 SubModules — all 24 permission sets

`src/Entity/SubModules.php`, every one `#[ORM\Column(type: Types::ARRAY, nullable: true)]`:

| # | Property | Domain area | Enforced by `UserAccessValidation`? |
|---|---|---|---|
| 1 | `daily_time_record` | DTR / attendance | ✅ in switch — ❌ never called |
| 2 | `subdivision` | Subdivision (org/project) | ✅ **enforced** (ProjectController ×5) |
| 3 | `division` | Division | ✅ **enforced** (ManpowerController ×4) |
| 4 | `department` | Department | ✅ **enforced** (ManpowerController ×4) |
| 5 | `phase` | Project phase | ✅ **enforced** (ProjectController ×6) |
| 6 | `owner` | Property owner | ✅ **enforced** (ProjectController ×4) |
| 7 | `models` | House model | ✅ **enforced** (ProjectController ×4) |
| 8 | `model_types` | Model type | ✅ **enforced** (ModelControllersController ×4) |
| 9 | `emp_settings` | Employee settings | ✅ in switch — ❌ never called |
| 10 | `shifts` | Work shifts | ✅ **enforced** (ShiftsController ×4) |
| 11 | `employee_projects` * | Employee↔project assignment | ✅ in switch — ❌ never called |
| 12 | `projects` | Projects | 🔴 **NOT in switch** |
| 13 | `emp_project` | Employee project | 🔴 **NOT in switch** |
| 14 | `emp_list` | Employee master list | 🔴 **NOT in switch** |
| 15 | `sss_config` | SSS contribution config | 🔴 **NOT in switch** |
| 16 | `pagibig_config` | Pag-IBIG config | 🔴 **NOT in switch** |
| 17 | `bir_config` | BIR / withholding tax | 🔴 **NOT in switch** |
| 18 | `philhealth_config` | PhilHealth config | 🔴 **NOT in switch** |
| 19 | `payroll` | Payroll processing | 🔴 **NOT in switch** |
| 20 | `payroll_reports` | Payroll reports | 🔴 **NOT in switch** |
| 21 | `leave_policy` | Leave policy | 🔴 **NOT in switch** |
| 22 | `emp_leaves` | Employee leave balances | 🔴 **NOT in switch** |
| 23 | `holiday_config` | Holiday configuration | 🔴 **NOT in switch** |
| 24 | `leave_request` | Leave requests | 🔴 **NOT in switch** |
| 25 | `leave_calendar` | Leave calendar | 🔴 **NOT in switch** |

\* 🔴 **`employee_projects` is a phantom.** `UserAccessValidation.php:85-87` calls
`$sub_module_access->getEmployeeProjects()`, but `SubModules` has **no such property**
(the real one is `emp_project` → `getEmpProject()`). This branch would throw
`Error: Call to undefined method`. It is unreachable today only because nothing passes
`'employee_projects'`.

> 🔴 **13 of the 24 submodules — including the entire payroll and leave subsystems and
> all statutory-contribution configs (SSS / Pag-IBIG / BIR / PhilHealth) — have permission
> flags that are stored, editable in the UI, and shipped to the browser at login, but are
> physically incapable of being enforced.** Passing any of them to `validateUserAccess`
> hits the `default:` branch (L88-94) and returns **HTTP 400 "Submodule not recognized"** —
> not a denial, a *malformed-request* error.

### B.6 `Types::ARRAY` storage

All 29 permission columns use Doctrine's **deprecated `Types::ARRAY`**, which persists via
PHP `serialize()` and reads via `unserialize()`.

> 🟠 Deprecated since DBAL 2.13 / removed direction in DBAL 4 — a **future upgrade blocker**.
> 🟠 **Deserialization surface:** any write path to these columns (SQL injection elsewhere,
> DB compromise, restored backup) becomes **PHP object injection** on the next read.
> `json` type would be the safe, queryable equivalent. Permissions are also **unqueryable
> in SQL** today — you cannot ask "which roles can delete payroll?" without unserialising
> every row in PHP.

### B.7 Enforcement: `UserAccessValidation` (`src/Service/UserAccessValidation.php`)

**It is a plain service called manually inside controller actions. It is NOT an event
listener, NOT a subscriber, NOT a voter, and NOT wired to the kernel.** `config/services.yaml`
gives it no tags — only autowiring.

Call convention (repeated ~38×):
```php
$validationResult = $this->validateAccess->validateUserAccess($request, 'division', 'view');
if ($validationResult['status'] === 'error') {
    return new JsonResponse($validationResult, $validationResult['code']);
}
```

Logic (L22-120):
1. `$token === null || $token->getUser() === 'anon.'` → 401.
2. `!$user_role || !$user_role->getMainModule()` → 403.
3. `switch ($submodule)` → pick the array (11 cases only).
4. `if (is_array($access))` → `!empty($access['can_' . $access_type])` → grant, else 403.
5. Fallthrough → 403 "Submodule access is not configured".

> 🟠 **Bug — `$token->getUser() === 'anon.'` is dead code.** In Symfony 6/7
> `getUser()` returns `?UserInterface`, never the legacy `'anon.'` string. The
> anonymous check never fires. (Harmless here because the firewall already rejects
> anonymous `/api` traffic, but it is a false sense of defence.)
> 🟠 If `$user` is not a `User` (impossible today), `getUserType()` would fatal.
> 🟠 **`$request` is accepted but never used** — dead parameter on every one of the 38 calls.
> 🟠 **No audit logging of denials.** `AuditTrailLog` is imported at the top of the file
> (L3) and `DateTimeImmutable`/`DateTimeZone` too — **all unused**. Copy-paste from
> `AuditLog.php`. Failed authorization attempts are invisible.
> ✅ **Fail-closed.** Every non-grant path returns an error; `!empty()` treats missing keys
> and `false` alike as deny. This part is correct.

### B.8 Enforcement coverage — the core finding

**280 routes. 38 permission checks. 4 controllers.**

| Controller | `UserAccessValidation` injected | `validateUserAccess()` calls |
|---|---|---|
| `ProjectController` | ✅ | **21** |
| `ManpowerController` | ✅ | **9** |
| `ModelControllersController` | ✅ | **4** |
| `ShiftsController` | ✅ | **4** |
| `AffiliatedCompanyController` | ✅ | **0** |
| `BIRController` | ✅ | **0** |
| `EmployeeLeavesController` | ✅ | **0** |
| `EmployeePayrollController` | ✅ | **0** |
| `EmployeePayrollProfileController` | ✅ | **0** |
| `LeaveRequestController` | ✅ | **0** |
| `PagibigController` | ✅ | **0** |
| `PayrollGenerationController` | ✅ | **0** |
| `PayrollGroupsController` | ✅ (twice) | **0** |
| `PayrollReportsController` | ✅ | **0** |
| `PayslipController` | ✅ | **0** |
| `PhilHealthController` | ✅ | **0** |
| `SSSController` | ✅ | **0** |
| `SalaryAdjustmentController` | ✅ | **0** |
| `TaxShieldController` | ✅ | **0** |

> 🔴🔴 **15 controllers inject `UserAccessValidation` into their constructor and never
> call it.** This is the single most dangerous pattern in the codebase: the dependency's
> presence makes the code *look* protected during review, while every route in those
> files is reachable by **any authenticated user**. This covers **the entire payroll
> subsystem** (`PayrollGenerationController` 58 KB, `PayrollReportsController` 88 KB,
> `EmployeePayrollProfileController` 45 KB — salaries, payslips, salary adjustments,
> tax shields) and **the entire leave subsystem**.

> 🔴 **A further 26 controllers don't even inject it** — including
> `EmployeeRecordsController`, `UsersController`, `SuperAdminController`,
> `DashboardController`, `NotificationsController`, `BlocksController`,
> `AttendanceController`, `DTRReportController`, `SyncWorkerController`.

> 🟠 Even in the 4 "protected" controllers, coverage is partial — `ProjectController`
> has 21 checks but far more routes, and two checks are **commented out**
> (`ProjectController.php:426`, `:1963`).

### B.9 Role codes (`user_code`)

`user_code` is a free-text `varchar(255)` on `UserType` with **no enum, no constant class,
no validation, and no uniqueness constraint at the DB level** (uniqueness is only checked
in application code at `SuperAdminController.php:101-107`).

**There are no fixtures, no seed migrations, and no reference data in the repo**, so the
authoritative role list lives only in the production database. The **only** role code
hardcoded anywhere in the source is:

```php
// ManpowerController.php:173  and  ManpowerController.php:271
$userType = $userTypeRepository->findOneBy(['user_code' => "SUR"]);
```

> 🔴 **`"SUR"` is a hardcoded magic role assigned to every employee account
> auto-provisioned by `ManpowerController`** — both the single-employee create path
> (L173) and the CSV bulk-import path (L271). If a DBA renames or deletes that
> `user_code`, single-create silently assigns `null` (no null-check at L174) while
> bulk-import silently `continue`s and **skips the row** (L272-275) — a silent
> partial-import data-loss bug.

**Which modules each role gets** is **runtime data, not code.** It is configured per-role
through `PUT /api/main-modules/{id}` and cannot be determined from the repository.
There is no "super-admin bypass" anywhere in `UserAccessValidation` — a super-admin is
simply a `UserType` whose 29 arrays happen to be all-`true`.

### B.10 The permission-corruption bug

`SuperAdminController::updateMainModules()` L378-404 calls `SubModules::setPermissions()`
**positionally** with 24 arguments. Compare against the signature:

| Position | `setPermissions()` parameter | Value actually passed (L388-390) |
|---|---|---|
| 11 | `$projects` | `$subModuleData['emp_project']` ❌ |
| 12 | `$emp_project` | `$subModuleData['projects']` ❌ |
| 13 | `$emp_list` | `$subModuleData['emp_list']` ✅ |

> 🔴 **Arguments 11 and 12 are transposed.** Every time an administrator saves a role via
> `PUT /api/main-modules/{id}`, the **`projects` permission is written into the
> `emp_project` column and vice-versa.** The admin UI then reads them back swapped.
> Granting "Projects: view" actually grants "Employee Project: view".
> (Neither is enforced server-side per §B.5, so today this corrupts the *frontend* menu
> only — but it silently poisons the stored data, and it will become an authorization
> bug the moment anyone wires those two submodules into the switch.)

Additional defects in the same method:
> 🟠 **L308-311 validates `isset()` for only `project`, `humanres`, `administration`, but
> L315 then iterates `['project','humanres','administration','payroll','emp_leaves']`.**
> A request omitting `payroll` or `emp_leaves` reaches `foreach ($data['payroll'] ...)`
> on an undefined key → PHP warning + `TypeError`, caught by the generic `catch` and
> surfaced as an opaque **500** instead of a 400.
> 🟠 `createUserType()` (L122-127) only ever passes 3 of the 5 main modules to
> `setPermissions()`, so `payroll` and `emp_leaves` silently take deny-all defaults even
> if the client supplied them.
> 🟠 Every `catch` block returns `$e->getMessage()` verbatim to the client →
> **internal error / SQL / path disclosure** (see §H).

### B.11 UserType CRUD is scattered and conflicting

There is **no `UserTypeController`**. Five endpoints across three controllers:

| Route | Method | Defined in | Notes |
|---|---|---|---|
| `/api/usertype/create` | POST | `LoginController:361` | Legacy. Reads `email`+`password` from body and **ignores them** — vestigial "admin verification" that was never implemented. Creates a `UserType` with **no `MainModules`/`SubModules`**, producing a role that fails `UserAccessValidation` step 2 forever. |
| `/api/user-types` | POST | `SuperAdminController:87` | The real one — creates UserType + MainModules + SubModules. |
| `/api/user-types` | GET | `UsersController:148` | Lists all, **including `removed = 1`** (no filter). |
| `/api/user-types-permission` | GET | `SuperAdminController:74` | Same list with the full permission tree (`groups: user_permissions`). |
| `/api/user-types/{id}` | PUT | `UsersController:213` | Updates `name` / `user_code` / `removed` only. **No uniqueness re-check on `user_code`** → can create a duplicate that breaks `findOneBy(['user_code' => 'SUR'])`. |
| `/api/user-types/{id}/archive` | PATCH | `UsersController:257` | Soft-delete: `setRemoved(1)`. |
| `/api/user-types/delete/{id}` | DELETE | `SuperAdminController:449` | **Hard delete.** Nullifies `user_type` on all attached users first (L462-466). |

> 🔴 **`deleteUserType()` is an unauthenticated-by-role mass-privilege-stripping button.**
> Any authenticated user can `DELETE /api/user-types/delete/{id}`. Deleting a role sets
> `user_type = NULL` for every user in it; those users can still log in (`isActive` is
> unaffected) but `LoginController` L128-130 then returns
> **500 "User type not found."** — locking out an entire class of employees.
> `cascade: ['persist','remove']` on `UserType.main_module` also destroys the
> `MainModules` + `SubModules` rows. **Irreversible, no audit log, no confirmation.**

> 🟠 Both a **soft-delete** (`removed`) and a **hard-delete** exist for the same entity,
> and `GET /api/user-types` ignores `removed` — so archived roles remain selectable in
> the UI.

### B.12 Privilege escalation via `UsersController::updateUser()`

```php
#[Route('/api/user/update/{id}', name: 'update_user')]     // ← no methods: restriction
public function updateUser(Request $request, int $id): JsonResponse
```

> 🔴🔴 **CRITICAL.** No ownership check, no role check. Any authenticated user may target
> **any** `{id}` and change that user's:
> - `password` (L73-78) — **arbitrary account takeover**
> - `email` (L81-83) and `username` (L69-71) — the login identifiers
> - `user_type` (L89-92) — **direct vertical privilege escalation**: set your own
>   `user_type` to the super-admin role id.
> - `is_active` (L64-67) — **disable any other user, including all admins (DoS)**
>
> 🔴 **The route declares no `methods:`**, so it answers **GET, POST, PUT, PATCH, DELETE,
> HEAD** alike. Full account takeover is therefore reachable as a plain
> `GET /api/user/update/1?...` — no preflight, trivially CSRF-able, and loggable in proxies.
>
> 🟠 `setUserType()` is passed the result of `->find($data['user_type'])` with **no
> null-check** (L90-91) — a bogus id silently nulls the user's role.
> 🟠 `setActive($data['is_active'])` is unvalidated — a string `"false"` is truthy in PHP.

### B.13 RBAC summary

| Question | Answer |
|---|---|
| How does User→role work? | `User.user_type` FK → `UserType.user_code` (free string) |
| Symfony roles/voters? | ❌ **none** — everyone is `ROLE_USER` |
| Permission flags | `can_view`, `can_add`, `can_edit`, `can_delete` (bool) |
| `route`/`key` field? | ❌ none — magic strings in a `switch` |
| Storage | `Types::ARRAY` (PHP `serialize()`), 29 columns, 2 tables |
| Enforcement mechanism | **Manual call** inside controller actions — no listener/voter |
| Coverage | **38 / 280 routes (13.6%)**, 4 / 45 controllers |
| Enforceable submodules | **11 of 24** (+1 phantom that would fatal) |
| Payroll / leave protected? | 🔴 **No** — injected but never called |
| Default posture | ✅ deny-all on create; 🔴 **allow-all in practice** for unchecked routes |

---

## C. EMPLOYEE CORE — `EmployeeRecords`

`src/Entity/EmployeeRecords.php` — **1,004 lines**, the central master record ("EMP 201 file").

### C.1 Scalar fields

| Field | Type | Null | Notes |
|---|---|---|---|
| `id` | int PK | – | auto |
| `first_name` | varchar(255) | **NO** | |
| `middle_name` | varchar(255) | yes | |
| `last_name` | varchar(255) | **NO** | |
| `extension` | varchar(255) | yes | Jr., Sr., III |
| **`employee_code`** | varchar(255) | **NO** | **business key** (see §C.4) |
| `birthdate` | datetime | **NO** | |
| `birth_place` | varchar(255) | yes | |
| `age` | smallint | **NO** | 🟠 **denormalised** — stored, never recomputed → goes stale |
| `gender` | varchar(255) | **NO** | free text |
| `civil_status` | varchar(255) | **NO** | free text |
| `email` | varchar(255) | yes | |
| `zip_code` | **smallint** | yes | 🟠 PH ZIPs are 4-digit; smallint max 32767 — works, but a leading-zero ZIP loses its zero |
| `area` | varchar(255) | yes | |
| `present_barangay` / `present_city` | varchar(255) | yes | current address |
| `same_address` | bool | yes | copy-present-to-permanent flag |
| `permanent_barangay` / `permanent_city` | varchar(255) | yes | |
| `telephone` / `cellphone` | varchar(255) | yes | |
| `date_hired` | datetime | yes | |
| **`employee_status`** | varchar(255) | **NO** | see §C.5 |
| `position` | **varchar(255)** | yes | 🔴 **free text, NOT a FK** — no `Position` entity exists |
| `employment_type` | varchar(255) | yes | free text |
| `contract_expiry_date` | datetime | yes | |
| `date_separated` | datetime | yes | |
| `probationary_date` | datetime | yes | |
| `regularization_date` | datetime | yes | |
| `archived` | bool | yes | soft-delete flag (see §C.6) |
| `profile_photo_path` | varchar(255) | yes | path string, not a blob |

> 🟠 **No `created_at` / `updated_at` / `created_by` on the master record.** There is no way
> to tell when an employee row was created or last modified except by mining `audit_trail_log`.
> 🟠 **`position` and `employment_type` are free-text strings**, so "Foreman", "foreman",
> and "Fore man" are three distinct positions. No lookup table, no validation, and they
> cannot be reported on reliably.
> 🟠 **`gender` and `civil_status` are unconstrained `varchar(255)`** — no enum, no
> `#[Assert\Choice]`.

### C.2 Relationships

| Relation | Cardinality | Target | Declared |
|---|---|---|---|
| `user` | **OneToOne** (owning, `cascade: persist, remove`) | `User` | L134-136 |
| `division` | ManyToOne | `Division` | L126-128 |
| `department` | ManyToOne | `Department` | L130-132 |
| `affiliated_company` | ManyToOne | `AffiliatedCompany` | L176-178 |
| `employeeAdditionalRecords` | OneToOne (inverse, `mappedBy: employee_code`) | `EmployeeAdditionalRecords` | L161-162 |
| `workers` | OneToMany | `Worker` | L152-153 |
| `employeeProjects` | OneToMany | `EmployeeProjects` | L158-159 |
| `employeeAttachments` | OneToMany | `EmployeeAttachments` | L167-168 |
| `loanHistories` | OneToMany | `LoanHistory` | L173-174 |
| `leaveRequests` | OneToMany | `LeaveRequest` | L183-184 |
| `yearlyEmployeeLeaves` | OneToMany | `YearlyEmployeeLeave` | L189-190 |
| `accountabilityRecords` | OneToMany | `AccountabilityRecords` | L195-196 |
| `employeeOvertimeRequests` | OneToMany | `EmployeeOvertimeRequest` | L201-202 |
| `dTRAdjutments` | OneToMany | `DTRAdjutments` [sic] | L207-208 |
| `notifications` | OneToMany (`recipient_employee_record`) | `Notifications` | L213-214 |
| `sender_notifications` | OneToMany (`sender_employee_record`) | `Notifications` | L219-220 |

**Payroll profile — inverted ownership.** `EmployeeRecords` has **no** `employeePayrollProfile`
property. The link is declared the other way round:
```php
// EmployeePayrollProfile.php:48-49
#[ORM\OneToOne(cascade: ['persist', 'remove'])]
private ?EmployeeRecords $employee_record = null;
```
> 🟠 A **unidirectional** OneToOne with no `inversedBy`. You cannot navigate
> `$employee->getPayrollProfile()`; every lookup must go through the repository. This
> asymmetry (vs. every other relation being bidirectional) is a frequent source of
> N+1 queries in the payroll controllers.

**Shift — reached through `User`, not `EmployeeRecords`.**
```php
// User.php:213-215
#[ORM\ManyToOne(inversedBy: 'users')] private ?Shifts $emp_shift = null;
```
> 🔴 **Work shift is an attribute of the login account, not the employee.** An employee
> with no `User` row (perfectly legal — `user` is nullable) **cannot have a shift**, which
> silently breaks DTR/attendance computation for them. Shift assignment also travels with
> `UsersController::updateUser()` (§B.12), meaning it inherits that endpoint's total lack
> of authorization. `Shifts` carries `start_time`, `end_time`, `name`,
> `lunch_break_duration`, `total_hours_minus_lunch`, `days_of_week` (`Types::ARRAY`), `archived`.

### C.3 `EmployeeAdditionalRecords` — the PII annex

OneToOne on `employee_code` (`cascade: persist, remove`). Holds **11 unstructured
`json`/array columns**: `employment_history`, `past_employment_record`,
`educational_background`, `seminars_trainings`, `assessments_exams`, `skills`, `awards`,
`licenses`, `dependents`, `violations`, `medical_drug_tests`; plus scalars
`school_graduated`, `course`, `career_band_level`, `career_global_grade`,
`cash_card_number`, `hmo_account`, and the four **government IDs**: `sss_number`,
`philhealth_number`, `pagibig_number`, `tin_number`.

> 🔴 **Highly sensitive PII stored entirely in plaintext** — government identifiers,
> bank/cash-card number, medical & drug-test results, disciplinary violations, and
> dependents. **No column-level encryption, no field-level access control, and no
> serialization-group separation from ordinary employee data.** Anything that serialises
> with `groups: 'employee'` can expose it — including the **unauthenticated**
> `/api/forget_password` response (§A.11).
> 🟠 The OneToOne property is confusingly **named `employee_code` but typed
> `EmployeeRecords`** (`EmployeeAdditionalRecords.php:17-20`) — it is an object reference,
> not the code string.

### C.4 Employee number scheme

> ⚠️ **There is no generator.** `employee_code` is taken **verbatim from the client**:
> ```php
> $employee->setEmployeeCode($data['employee_code']);   // ManpowerController.php:119
> ```
> No `sprintf`, `str_pad`, sequence, or `MAX(id)+1` logic exists anywhere in `src/`.
> The `EMP002`-style format is a **frontend/data-entry convention only** — the backend
> accepts any string.
>
> Uniqueness is enforced **only in application code** (`ManpowerController.php:95-99`,
> returns `409 CONFLICT`), **not by a DB unique index** → a race between two concurrent
> creates inserts duplicates. Because `employee_code` is used as a lookup key
> (`findOneBy(['employee_code' => ...])` in `EmployeeRecordsController` L240, and it is
> also copied into `User.username` at `ManpowerController.php:165`), duplicates corrupt
> attachment upload, DTR matching, and login.
>
> The same applies to `email` — checked in code (L102-110) but with **no unique constraint**.

### C.5 `employee_status` values

`varchar(255)`, **no enum / no `Assert\Choice`**, assigned straight from the request
(`ManpowerController.php:139`, `:308`, `:461`). Values observable in source:

| Value | Where |
|---|---|
| `Separated` | `ManpowerController.php:145` |
| `Probationary` | `ManpowerController.php:146` |
| `Regular` | `ManpowerController.php:147` |
| `Active` | `ManpowerController.php:167` |

> 🟠 **`employee_status` conflates two orthogonal concepts** — *employment stage*
> (Probationary / Regular) and *lifecycle state* (Active / Separated) — in one free-text
> column. Any typo (`"regular"`, `"REGULAR"`) creates a new de-facto status that silently
> drops the employee out of status-filtered payroll and headcount queries.
> There are three independent, unsynchronised "is this person gone?" signals:
> `employee_status`, `date_separated`, and `archived`.

### C.6 Soft delete / status

Three separate mechanisms, none authoritative:

| Flag | Entity | Semantics |
|---|---|---|
| `EmployeeRecords.archived` (`bool`, nullable) | employee | HR soft-delete |
| `User.archived` (`bool`, nullable) | login account | account soft-delete |
| `User.removed` (`int`, default `0`) | login account | **second, redundant** soft-delete |
| `User.is_active` (`bool`, default `true`) | login account | login gate (checked only at login) |
| `User.status` (`int`, nullable) | login account | 🟠 **never read or written anywhere** — dead column |
| `UserType.removed` (`smallint`) | role | role soft-delete |

> 🟠 **`User` carries four overlapping state columns** (`archived`, `removed`, `is_active`,
> `status`) with no documented precedence. `removed` and `status` appear to be dead.
> 🟠 All are **nullable booleans** → tri-state logic (`null` ≠ `false`), so
> `WHERE archived = 0` silently excludes every legacy row where `archived IS NULL`.
> 🔴 **Archiving an employee does not disable their login** (`EmployeeRecords.archived`
> and `User.is_active` are independent), and disabling a login does not invalidate live
> JWTs (§A.5). A separated employee can retain API access indefinitely.

### C.7 Attachments & profile photo

`POST /api/employee/upload_attachment` (`EmployeeRecordsController.php:215`)
Accepts a **JSON body**, not `multipart/form-data`:
`employee_code`, `type`, `attachment_name`, `attachment_size`, `file`, `original_file_name`.
`EmployeeAttachments.file` is `varchar(255)` → a **path/reference string**, not the bytes.

> 🔴 **`attachment_size` is client-supplied and stored verbatim** (`varchar(255)`) — it is
> never measured server-side. Any size can be claimed.
> 🔴 **The server never sees, validates, or stores the actual file.** No MIME check, no
> extension whitelist, no size limit, no virus scan, no path-traversal guard on
> `file` / `original_file_name`. The upload must therefore happen out-of-band and the
> client simply *asserts* the resulting path — any authenticated user can point an
> attachment record at an arbitrary path.
> 🟠 Dead code at L246-249: `$employeeAttachment = $repo->findOneBy(...)` is immediately
> overwritten by `new EmployeeAttachments()` — the "find or create" comment is a lie;
> it always creates, so re-uploading duplicates rows.
> 🟠 L228: returns `['error' => 'Employee not found', JsonResponse::HTTP_NOT_FOUND]` —
> the status constant is passed as an **array element, not the HTTP status**, so this
> error is returned with **HTTP 200**.
> 🔴 L284: `"There's an error in code: ".$e` string-casts the exception → **full message
> + stack trace + file paths returned to the client**.

`POST /api/employee/profile_photo_add/{empId}` (L372) — same pattern: takes a
`profile_photo_path` **string** from the body and writes it to the record with no
validation and **no ownership check** (any authenticated user can set any employee's photo).

### C.8 Employee provisioning & the default password

`ManpowerController` creates the `User` alongside the `EmployeeRecords`:

```php
// ManpowerController.php:161-179
$password = $employee->getEmail() ? $employee->getEmail() : '';
$user = new User();
$user->setEmail($employee->getEmail());
$user->setUsername($employee->getEmployeeCode());
$user->setActive(true);
...
$userType = $userTypeRepository->findOneBy(['user_code' => "SUR"]);
$user->setUserType($userType);
$hashedpass = $this->passhasher->hashPassword($user, $password);
```

> 🔴🔴 **CRITICAL — every auto-provisioned employee's initial password IS their own email
> address.** Combined with `findOneByEmailOrUsernameOrPhone`, the credential pair is
> `identifier = <email>, password = <email>`. Employee emails are, by definition, known
> to colleagues and usually derivable from the name. **Any employee's account can be
> logged into by anyone who knows their email**, unless the user has since changed it —
> and nothing forces a change: there is no `must_change_password` flag, no first-login
> interstitial, and no expiry.
> 🔴 **If the employee has no email, the password is the empty string `''`** — hashed and
> accepted. `LoginController` L101 rejects an empty `password` in the request, so the
> account is *un-loginnable* rather than open, but it is still a broken account.
> 🔴 The same logic is repeated in the **CSV bulk-import** path
> (`ManpowerController.php:280`: `hashPassword($user, $employeeData['email'])`) — so a
> single CSV upload can mint hundreds of accounts whose password is their email.
> 🟠 No null-check on `$userType` in the single-create path (L173-174) → a role-less user.

---

## D. ORG STRUCTURE & CONSTRUCTION DOMAIN

This is a **residential/subdivision construction** HRIS. Two overlapping hierarchies exist:
an **HR hierarchy** and a **physical construction hierarchy**.

```
HR:            Division ──< Department ──< EmployeeRecords
                                              │
Construction:  Subdivision ──< Phase ──< Blocks ──< Lots
                     │            │
                  Project ────────┘        Model ──< ModelTypes
                     │                        │
               EmployeeProjects ──────────────┘
                     │
                  Owner / Category
```

### D.1 `Division` — `src/Entity/Division.php`

Top of the HR hierarchy. Owns many `Department`s and many `EmployeeRecords`
(`EmployeeRecords.division`, ManyToOne). In the construction business this is the
top-level operating group (e.g. Construction, Sales & Marketing, Admin/Finance).

> ❌ **No `DivisionController` exists.** All Division CRUD is in **`ManpowerController`**:
> view (L1089), add (L1027), edit (L1140), delete (L1210) — and these are among the
> **few** endpoints that *do* call `validateUserAccess(..., 'division', ...)`. ✅

### D.2 `Department` — `src/Entity/Department.php`

Second HR level; belongs to a `Division`, owns many `EmployeeRecords`
(`EmployeeRecords.department`, ManyToOne). E.g. Carpentry, Masonry, Steelworks,
Electrical, Warehouse, Accounting.

> ❌ **No `DepartmentController` exists.** CRUD lives in **`ManpowerController`**:
> view (L786), add (L830), edit (L910), delete (L980) — all four RBAC-checked with
> `'department'`. ✅

### D.3 `Subdivision` — `src/Entity/Subdivision.php`

The **housing development / village** being built — the top of the physical hierarchy
(e.g. "Woodhills Residences"). Managed by `ProjectController`
(view L83, add L167, edit L226/L297, delete L358) — RBAC-checked with `'subdivision'`. ✅

### D.4 `Phase` — `src/Entity/Phase.php`

A **construction phase / stage of a subdivision** (Phase 1, Phase 2 …). Standard practice
in PH subdivision development: land is released and built out in numbered phases.
Managed by `ProjectController` (view L1441/L1492, add L1542, edit L1686/L1861,
delete L1818) — RBAC-checked with `'phase'`. ✅

### D.5 `Blocks` — `src/Entity/Blocks.php` + `BlocksController.php`

A **block within a phase** — the classic PH address unit "Block 5, Lot 12". Sits between
`Phase` and `Lots`.

`BlocksController` (3.7 KB) is **read-only**, only two routes:

| Route | Method | Line |
|---|---|---|
| `api/blocks` | GET | 43 |
| `api/blocks/{block_id}` | GET | 66 |

> 🟠 **No create/update/delete** — blocks must be seeded directly in the DB or created via
> `ProjectController`. An incomplete CRUD surface.
> 🟠 **No RBAC** — `UserAccessValidation` is not injected. Any authenticated user can
> enumerate all blocks.

### D.6 `Lots` — `src/Entity/Lots.php`

The individual **saleable lot** inside a block. No dedicated controller.

### D.7 `Model` / `ModelTypes`

- **`Model`** (`src/Entity/Model.php`) — a **house model / floor plan** offered in the
  development (e.g. "Bungalow A", "Two-Storey Duplex").
- **`ModelTypes`** (`src/Entity/ModelTypes.php`) — the **variant/classification** of a
  model (e.g. Single-Attached, Single-Detached, Townhouse, Duplex).

`Model` CRUD → `ProjectController` (view L1298, add L1346, edit L1386, delete L1420),
RBAC `'models'`. ✅
`ModelTypes` CRUD → **`ModelControllersController`** (view L63, add L102, edit L153,
delete L211), RBAC `'model_types'`. ✅ There is also a thin `ModelTypeController.php` (4.3 KB).

> 🟠 Three near-identically named files — `ModelControllersController.php` (10.3 KB),
> `ModelTypeController.php` (4.3 KB), and `Model`/`ModelTypes` handling inside
> `ProjectController` — a naming/ownership mess that invites divergent behaviour.

### D.8 `Owner` — `src/Entity/Owner.php`

The **property owner / buyer / client** of a lot or unit — the counterparty in the
construction contract. CRUD → `ProjectController` (view L1123, add L1167, edit L1220,
delete L1273), RBAC `'owner'`. ✅

### D.9 `Category` — `src/Entity/Category.php`

A **work/cost category** used to classify project scope and labour
(e.g. Structural, Finishing, Plumbing). Imported by `SuperAdminController`
and `ProjectController`.

### D.10 `Project` / `ProjectType` — `src/Entity/Project.php`

`Project` is the **construction job/contract** unit that work and manpower are booked
against. `ProjectType` classifies it (e.g. Horizontal / Vertical, Residential / Commercial).
`ProjectController` is **120 KB** and effectively owns the entire construction domain —
Subdivision, Phase, Owner, Model, Project, Category.

> 🟠 A 120 KB / ~2,400-line controller with 6+ distinct aggregate roots is the single
> largest maintainability liability in the org-structure area.

### D.11 `EmployeeProjects` — `src/Entity/EmployeeProjects.php`

The **assignment join** between an employee and a project — "who is deployed where".
`EmployeeRecords.employeeProjects` (OneToMany) ←→ `EmployeeProjects.employee` (ManyToOne).
Serialization group `emp_projects`.

Gated (in principle) by `User.is_assignable_proj` (`User.php:209-211`), settable via
`UsersController::updateUser()` and at creation in `ManpowerController` (`is_assignable`).

> 🔴 Its permission set is the **swapped pair** from §B.10 (`emp_project` ⇄ `projects`)
> and **neither is in the `UserAccessValidation` switch** — employee-to-project assignment
> is completely unauthorized server-side.
> 🔴 `UserAccessValidation` L85-87 references a non-existent `getEmployeeProjects()`
> (§B.5) — the one branch that *was* meant to guard this would fatal.

### D.12 `Worker` / `WorkerLogs` / `SyncConnection`

`Worker` (`EmployeeRecords.workers`, OneToMany) and `WorkerLogs` are the
**biometric time-clock** side of the house — the raw punch data pulled from the device
database. `SyncConnection` stores the **credentials of that second database**
(see §H-6). `SyncWorkerController` (19.7 KB) drives the import.

> 🟠 A `Worker` is a *second* representation of a person, keyed to `EmployeeRecords` — so
> identity is split across `User`, `EmployeeRecords`, and `Worker`, each with its own
> lifecycle flags. `User.is_worker` (`User.php:227-229`) and
> `User.biometricData` (`varchar(999)`) are the bridging fields.

---

## E. NOTIFICATIONS & AUDIT TRAIL

### E.1 `Notifications` entity — `src/Entity/Notifications.php`

| Field | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `recipient_department` | ManyToOne → `Department` | 🟠 `inversedBy: 'recipient_division'` — **wrong inverse name** (copy-paste) |
| `recipient_division` | ManyToOne → `Division` | `inversedBy: 'notifications'` |
| `action` | varchar(255) null | short title / action message |
| `description` | varchar(255) null | 🟠 **only 255 chars** for a message body — will silently truncate |
| `datetime` | datetime null | |
| `notification_type` | **int** null | magic number, see §E.3 |
| `recipient_employee_record` | ManyToOne → `EmployeeRecords` | |
| `sender_employee_record` | ManyToOne → `EmployeeRecords` | |

> 🔴 **There is no `is_read` / `read_at` / `seen` field.** Notifications can never be
> marked as read — the feature is structurally incomplete. The frontend can only ever
> show a permanently growing list.
> 🟠 No `archived`/soft-delete either; `DELETE /api/notifications/delete/{id}` hard-deletes.

### E.2 `NotificationService` — `src/Service/NotificationService.php`

Three public entry points, all fan-out to the private `setNewNotification()`:

| Method | Purpose |
|---|---|
| `createNotification($division, $department, $actionMsg, $description, $datetime, $type)` | Caller-specified target scope |
| `createNotificationUsingToken($actionMsg, $description, $datetime, $type)` | Scope derived from the **sender's own** division/department |
| `createNotificationForSpecificUser($recipientEmployee, $actionMsg, $description, $datetime)` | Single recipient, hardcoded type `"4"` |

Consumers: `EmployeePayrollProfileController`, `LeaveRequestController`,
`PayrollGenerationController`, `ManpowerController`.

### E.3 Notification type codes (magic ints, no enum)

| `$type` string | `createNotification()` | `createNotificationUsingToken()` | Recipients queried |
|---|---|---|---|
| `ALL` | `0` | `0` | `employee_status='Active'` **AND division AND department** |
| `DEP_ONLY` | `1` | `1` | Active + department |
| `DIV_ONLY` | `2` | `2` | Active + division |
| `DIV_DEP` | **`2`** 🔴 | **`3`** 🔴 | Active + **department only** |
| (specific user) | `"4"` (string) | — | one employee |

> 🔴 **`DIV_DEP` is assigned type `2` in one method and `3` in the other** (L62 vs L111) —
> the same logical event is stored under two different codes depending on which entry
> point fired. Any consumer filtering on `notification_type` gets inconsistent results.
> 🔴 **`DIV_DEP` ignores the division entirely** — despite the name, both implementations
> query `findBy(['employee_status' => 'Active', 'department' => $dept])`, making it a
> duplicate of `DEP_ONLY` with a different code.
> 🔴 **`ALL` does not mean all** — it filters by division *and* department, so it is the
> narrowest scope, not the broadest. The name is actively misleading.
> 🟠 `createNotificationForSpecificUser` passes the type as the **string** `"4"` into an
> `int` column (L137) — type juggling into a typed field.
> 🟠 `default:` sets `$notifType = 0` but then **falls through to `flush()` without
> creating anything** — an unknown type silently no-ops.

### E.4 Recipient resolution bug

```php
// NotificationService.php:36-38 (repeated at :83-85 and :132-134)
$senderEmployeeRecordId = $this->entityManager->getRepository(EmployeeRecords::class)
                               ->findOneBy(['user' => $user->getId()]);
$senderEmployee = $this->entityManager->getRepository(EmployeeRecords::class)
                       ->find($senderEmployeeRecordId);
```

> 🔴 **`findOneBy()` already returns an `EmployeeRecords` entity**, but the result (named
> `...RecordId`, as if it were an int) is then passed **as an identifier** to `find()`.
> Doctrine is being asked to look up an entity *by an entity object*. At best this is a
> redundant second query; at worst it throws or coerces unpredictably. The variable
> naming shows the author believed `findOneBy` returned a scalar.
> 🟠 If the acting user has **no `EmployeeRecords`** (e.g. a pure admin account), the
> `if ($senderEmployeeRecordId)` guard silently skips notification creation entirely —
> **no error, no log**. Payroll and leave events raised by admins vanish.

### E.5 🔴 All notification email is hardcoded to one developer

```php
// NotificationService.php:158-167
private function sendNotificationEmail($email, $subject, $employeeName, $message)
{
    $emailContent = (new Email())
        ->from('noreply@example.com')
        // ->to($email)                        // ← THE REAL RECIPIENT, COMMENTED OUT
        ->to('lquisim@techrostrum.com')        // ← hardcoded developer address
        ->subject($subject)
        ->html('<h3>Hello '.$employeeName.',</h3><br><p>'.$message.'</p><br><br>');
    $this->mailer->send($emailContent);
}
```

> 🔴🔴 **Every notification email the system sends — payroll released, leave approved/
> rejected, employee events — is delivered to `lquisim@techrostrum.com` and to nobody
> else.** The `$email` parameter is accepted and discarded. This is simultaneously:
> - a **total functional failure** (no employee ever receives a notification email), and
> - a **continuous PII leak** — every employee's last name and every payroll/leave action
>   message is mailed to a single individual's inbox.
>
> 🔴 `from: 'noreply@example.com'` is a placeholder domain → SPF/DKIM will fail; mail is
> spam-foldered or rejected.
> 🔴 **HTML injection / email-header risk:** `$employeeName` and `$message` are
> concatenated raw into `->html()` with no escaping.
> 🔴 **Mail is sent synchronously inside the fan-out loop** (`setNewNotification()` L153,
> called once per recipient, *before* `persist()`). Notifying a 200-person department
> performs 200 blocking SMTP round-trips inside one HTTP request → guaranteed timeout.
> Symfony Messenger is **not** installed, so there is no async transport.
> 🔴 **No try/catch.** A single SMTP failure throws, aborting the whole operation — and
> because `flush()` happens after the loop, **the business action that triggered the
> notification is rolled back by a mail server hiccup.**
> 🔴 SMTP credentials are committed in `.env`:
> `MAILER_DSN=smtp://japarece@techrostrum.com:zhtlkdfcbnykqzfs@smtp.gmail.com:587?encryption=tls`
> — a **live Gmail app password in version control**. (It is also placed under the
> `###> nelmio/cors-bundle ###` block, so `composer` recipe updates may clobber it.)

### E.6 `NotificationsController` — `/api/notifications`

| Route | Method | Line | RBAC | Ownership check |
|---|---|---|---|---|
| `/list` | GET | 25 | ❌ | ❌ |
| `/create` | POST | 48 | ❌ | ❌ |
| `/find/{id}` | GET | 73 | ❌ | ❌ |
| `/find-by-employee/{userId}` | GET | 97 | ❌ | ❌ |
| `/update/{id}` | PUT | 124 | ❌ | ❌ |
| `/delete/{id}` | DELETE | 149 | ❌ | ❌ |

The controller injects **only** `EntityManagerInterface` — no `AuditLog`, no
`UserAccessValidation`.

> 🔴 **`GET /api/notifications/list` returns every notification in the entire system**
> (`findAll()`, L28) to any authenticated user — cross-department payroll and leave
> messages for all employees. **No pagination either** → unbounded response.
> 🔴 **`GET /find-by-employee/{userId}` has no ownership check** — any authenticated user
> reads any other user's notification inbox by incrementing `{userId}`. **IDOR.**
> 🔴 Same route, worse: `findOneBy(['user' => $userId])` may return `null`, then L100
> calls `$employeeRecord->getId()` → **fatal `Error` on null** for any `userId` without an
> employee record. Unhandled 500.
> 🟠 **Duplicate route name `find_notification`** is declared twice (L73 and L97). Symfony
> silently keeps the last definition, so URL generation for `find_notification` is broken.
> 🔴 `create` / `update` call `->find($data['x'] ?? null)` — passing `null` to
> `EntityManager::find()` and assigning the result unchecked. In `update` (L138-145),
> **every** relation is overwritten from the payload with `?? null` fallback, so a partial
> PUT **wipes** `recipient_department`, `recipient_division`, `recipient_employee_record`,
> and `sender_employee_record`. `action`/`description` correctly fall back to the current
> value, but the relations do not — inconsistent and destructive.
> 🔴 `create` lets any authenticated user **forge `sender_employee_record`** — send a
> notification that appears to come from the CEO.
> 🟠 No audit logging on any notification mutation.

### E.7 `AuditTrailLog` — `src/Entity/AuditTrailLog.php`

| Field | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `ip_address` | varchar(255) null | from `$request->getClientIP()` |
| `transactions` | **TEXT** null | JSON blob (see below) |
| `datetime` | datetime **NOT NULL** | 🟠 carries a stray `#[ORM\JoinColumn(nullable:true)]` (L24) — meaningless on a scalar column, and contradicts the non-nullable `Column` |
| `user` | ManyToOne → `User` | 🟠 type-hinted lowercase `?user` (L28) — works only via PHP's case-insensitive class names |

### E.8 `AuditLog` service — `src/Service/AuditLog.php`

```php
public function addAuditLog($request, $apiResponse, $apiurl, $action)
{
    $currentDateTime = new DateTimeImmutable('now', new DateTimeZone('Asia/Manila'));
    $ipaddress = $request->getClientIP();
    $token = $this->tokenStorage->getToken();
    $user = "";
    if ($token !== null && $token->getUser() !== 'anon.') { $user = $token->getUser(); }
    $transaction = [
        'api_url'        => $apiurl,
        'action'         => $action,
        'client_request' => $request->getContent(),   // ← RAW REQUEST BODY
        'api_response'   => $apiResponse,
    ];
    $newLog = new AuditTrailLog();
    $newLog->setUser($user);
    ...
}
```

**What is logged:** `api_url`, a free-text `action` label, the **entire raw request body**,
and a caller-supplied response summary — plus client IP, actor, and Manila-time timestamp.

> 🔴🔴 **Plaintext credentials are written to the audit table.** `client_request` is
> `$request->getContent()` verbatim. `LoginController::login()` calls `addAuditLog` (L182),
> so **every login attempt persists `{"identifier":"...","password":"<PLAINTEXT>"}`** into
> `audit_trail_log.transactions`. The same applies to `UsersController::updateUser()`
> (password changes) and `LoginController::signup()`-adjacent flows. Anyone with read
> access to that one table harvests live passwords for the whole company.
> 🔴 **`setUser("")` — an empty string, not `null`.** When there is no token, a `string` is
> passed to a `?User` typed setter → **`TypeError`** in PHP 8. Unauthenticated audit
> writes crash. (`login()` calls this *after* authentication succeeds, so it survives —
> but any unauthenticated call site would 500.)
> 🟠 The `'anon.'` comparison is the same dead legacy check as in `UserAccessValidation` (§B.7).
> 🟠 `getClientIP()` **trusts `X-Forwarded-For`** unless `framework.trusted_proxies` is
> configured — and it is **not** (`config/packages/framework.yaml` has no `trusted_proxies`).
> **Audit IP addresses are attacker-spoofable.**
> 🟠 `flush()` is called inside `addAuditLog()`, so an audit write **flushes the caller's
> in-flight unit of work**, potentially committing partial business state early — and it
> runs *inside* controller transactions in several places.
> 🟠 No try/catch: an audit failure aborts the business operation.
> 🟠 No retention policy, no index on `datetime`/`user`, `transactions` is unbounded TEXT.

### E.9 Who sees the audit trail

> 🔴 **Nobody. There is no read path.** `AuditTrailLog` is **write-only**:
> - no `AuditTrailLogController` exists;
> - repo-wide, `AuditTrailLog` appears only in `AuditLog.php` (write),
>   `UserAccessValidation.php` (**unused import**), `NotificationService.php`
>   (**unused import**), the entity, and `User.auditTrailLogs` (never read);
> - `AuditTrailLogRepository` has no custom finders.
>
> The audit trail is accumulating plaintext passwords and full request bodies **that no
> application feature can ever display**. It is pure liability: all of the risk of an
> audit log, none of the benefit.

> 🟠 **Coverage is inconsistent.** Logged: login, revalidate-session (mislabelled as
> "User Login"), user update, attachment upload, profile photo, view-connections. **Not
> logged:** password reset, signup, all UserType/permission changes (create/update/
> archive/**delete**), all notification mutations, dashboard. **The most
> security-relevant operations in the system are the ones that are not audited.**

---

## F. DASHBOARD

`src/Controller/DashboardController.php` — 81 lines, **a single route**.

```php
#[Route('/api/dashboard', name: 'app_dashboard')]      // ← no methods: restriction
public function dashboardModulesCount(Request $request): JsonResponse
```

### F.1 The 9 KPIs

| Response key | Source | Repository method |
|---|---|---|
| `employeeRecordsCount` | `EmployeeRecords` | `countByNotArchived()` |
| `dtrRecordsDailyCount` | `WorkerLogs` | `countTodayLogs()` |
| `divisionCount` | `Division` | `countByNotArchived()` |
| `departmentCount` | `Department` | `countByNotArchived()` |
| `manpowerAssignmentCount` | `EmployeeProjects` | `countByNotArchived()` |
| `projectCount` | `Project` | `countByNotArchived()` |
| `subdivisionCount` | `Subdivision` | `countByNotArchived()` |
| `ownersCount` | `Owner` | `countByNotArchived()` |
| `facilitiesCount` | **`Model`** | `countByNotArchived()` |

All are simple **non-archived row counts**; the only time-scoped metric is
`countTodayLogs()` (today's biometric punches). No aggregation, no money, no trends,
no date-range parameters, no per-project or per-department breakdown.

### F.2 Observations

> 🟠 **`facilitiesCount` is derived from the `Model` (house-model) repository** — the label
> and the data disagree. Either a copy-paste error or a renamed concept never propagated.
> 🟠 **`countByNotArchived()` is duplicated across 7 repositories** rather than living in a
> shared trait/base repository.
> 🟠 The `archived` columns are **nullable booleans** (§C.6), so these counts depend on how
> each repository handles `NULL` — likely `= 0`, which would **exclude every legacy row**
> where `archived IS NULL` and silently under-report headcount.
> 🔴 **No RBAC and no scoping.** Company-wide headcount and project counts are returned to
> **any** authenticated user, including the lowest-privilege `"SUR"` accounts
> auto-created for every employee (§C.8).
> 🔴 **No `methods:` restriction** → answers GET/POST/PUT/DELETE alike.
> 🟠 **9 separate `COUNT` queries per page load**, none cached, despite APCu pools being
> configured for Doctrine.
> 🟠 `$request` is injected and **never used**; `jwtManager`, `tokenStorage`, and
> `serializer` are injected and never used; `passhasher`, `auditlog`, `validator`
> properties are **declared but never assigned** (L30-32) → they are `null`, and the
> constructor doesn't accept them. Dead scaffolding.
> 🟠 **No audit logging.**
> 🟠 The comment `// Adjust if method name is different` is repeated **8 times** —
> unfinished code shipped as-is.

---

## G. MISC — SuperAdmin & Permission Controllers

### G.1 `SuperAdminController` (22.8 KB)

| Route | Method | Line | What it manages |
|---|---|---|---|
| `/api/super_admin/connections` | GET | 51 | Lists `SyncConnection` rows — the **biometric DB credentials** |
| `/api/user-types-permission` | GET | 74 | All UserTypes **with the full permission tree** (`groups: user_permissions`) |
| `/api/user-types` | POST | 87 | Create UserType + MainModules + SubModules (deny-all defaults) |
| `/api/main-modules` | POST | 185 | Create a bare MainModules row |
| `/api/sub-modules` | POST | 243 | Create a bare SubModules row |
| `/api/main-modules/{id}` | PUT | 300 | **The real permission editor** — updates MainModules + all 24 SubModules |
| `/api/user-types/delete/{id}` | DELETE | 449 | **Hard-delete** a UserType |

> 🔴🔴 **Despite the name, there is not a single super-admin check in this controller.**
> No `isGranted`, no `UserAccessValidation` (not even injected), no `user_code`
> comparison. **Every route is reachable by any authenticated user** — including the
> `"SUR"` role auto-assigned to every rank-and-file employee (§C.8).
> **Any employee can grant themselves every permission in the system** via
> `PUT /api/main-modules/{id}`, or delete every role via `DELETE /api/user-types/delete/{id}`.
> This is the single highest-impact authorization gap in the codebase.

> 🔴 **`GET /api/super_admin/connections` discloses second-database connection details.**
> It serialises all `SyncConnection` rows with `groups: 'sync_conn'`. Checking
> `src/Entity/SyncConnection.php`, that group covers **`username` (L18), `dbname` (L25)
> and `host` (L29)** — the `password` field (L21-22) is **not** in the group, so the
> password itself is *not* leaked. ✅ But **hostname, database name and DB username of the
> biometric production database are handed to any authenticated caller**, which is
> three-quarters of a credential set and a direct lateral-movement roadmap.
> 🟠 It then writes that serialised payload into the **audit log** (L60), persisting
> DB credentials into `audit_trail_log.transactions` as well.

> 🟠 `createMainModules` / `createSubModules` (L185, L243) create **orphan** rows not
> attached to any `UserType` — dead data with no cleanup path.
> 🟠 `createSubModules` validates only `daily_time_record` and `subdivision` but
> `setPermissions()` receives just those two positionally, defaulting the other 22.
> 🟠 Every `catch (\Exception $e)` returns `'error' => $e->getMessage()` to the client
> (L175-178, L237-240, L295-298, L434-437, L478-481) → **internal error disclosure**.
> 🟠 The `$validator` and `$passhasher` dependencies are injected and never used.
> 🟠 See §B.10 for the **swapped `projects`/`emp_project` argument bug** in `updateMainModules`.

### G.2 `PermissionController` (1.6 KB) — an empty stub

```php
#[Route('/api/permission', name: 'app_permission')]     // no methods: restriction
public function index(): JsonResponse
{
    return $this->json([
        'message' => 'Welcome to your new controller!',
        'path' => 'src/Controller/PermissionController.php',
    ]);
}
```

> 🟠 **Unmodified `make:controller` scaffolding committed to the repo.** It manages
> nothing. Its six injected dependencies (`EntityManagerInterface`,
> `UserPasswordHasherInterface`, `JWTTokenManagerInterface`, `AuditLog`,
> `ValidatorInterface`, `SerializerInterface`) are all unused.
> 🟠 Actively **misleading**: a reviewer looking for the permission subsystem finds
> `PermissionController` and concludes permissions are handled there, when the real logic
> is in `SuperAdminController` + `UsersController` + `UserAccessValidation`.
> 🟠 It **leaks the server-side file path** in its response body.

---

## H. WEAK SPOTS

Severity: 🔴🔴 critical · 🔴 high · 🟠 medium

### H-1. 🔴🔴 Public, unauthenticated, **mutating** endpoints

`access_control` only guards `^/api`. Controllers **without a class-level `/api` prefix**
that declare non-`/api` routes fall through to the `main` firewall — `lazy: true`, **no
authenticator** → anonymous. Complete list:

| Route | Methods | Controller | Impact |
|---|---|---|---|
| `/signup` | **POST + GET** | `LoginController:327` | 🔴🔴 Anonymous account creation with **self-chosen role** (§A.12) |
| `/sync/worker` | **ANY** (no `methods:`) | `SyncWorkerController:30` | 🔴🔴 Anonymous trigger of the full biometric DB sync — mass writes to `worker` / `worker_logs` |
| `/check/emp/dtr` | **ANY** (no `methods:`) | `CheckEmpDtrController:34` | 🔴 Anonymous DTR inspection |
| `/salary/adjustments` | GET | `SalaryAdjustmentController:59` | 🔴🔴 **Anonymous read of every salary adjustment** |
| `/salary/adjustment/{id}` | GET / **PUT** / **DELETE** | `SalaryAdjustmentController:67,79,108` | 🔴🔴 **Anonymous read, modify and delete of salary data** |
| `/tax_shield` | **POST** | `TaxShieldController:34` | 🔴🔴 Anonymous creation of tax-shield records |
| `/tax_shield/{id}` | GET / **PUT** / **DELETE** | `TaxShieldController:54,73,97` | 🔴🔴 Anonymous read/modify/delete |

> **`SalaryAdjustmentController` is the clearest illustration of the bug:** `create` is
> correctly at `/api/salary/adjustment` (protected), while `list`, `show`, `update` and
> `delete` were written as `/salary/...` — **a single missing `/api` prefix exposes
> compensation data to the internet.** Both controllers also inject
> `UserAccessValidation` and never call it (§B.8), so even the `/api` route is unguarded.

**Fix direction:** invert the default — `- { path: ^/, roles: IS_AUTHENTICATED_FULLY }`
after the explicit `PUBLIC_ACCESS` allow-list, so a forgotten prefix fails *closed*.

### H-2. 🔴🔴 Unauthenticated account takeover via password reset

`POST /api/forget_password` returns the reset token **in the response body**, no email is
sent, and `resetPassword()` **never checks `token_expiry`**. The token is also a fully
valid Lexik JWT usable directly as a Bearer credential. The response additionally embeds
the victim's complete `EmployeeRecords`. See §A.11.

### H-3. 🔴🔴 Authenticated privilege escalation — three independent paths

1. **`POST /api/revalidate-session`** with any `{"user_id": N}` mints a 24-hour JWT for
   that user. No ownership check. (§A.7)
2. **`/api/user/update/{id}`** (any HTTP verb) lets any user rewrite any other user's
   `password`, `email`, `username`, `is_active`, and **`user_type`**. (§B.12)
3. **`PUT /api/main-modules/{id}`** in `SuperAdminController` has **no super-admin check** —
   any authenticated user can grant their own role every permission. (§G.1)

### H-4. 🔴 Missing authorization is the norm, not the exception

- **38 of 280 routes (13.6%)** call `validateUserAccess`.
- **15 controllers inject `UserAccessValidation` and never call it** — including the whole
  payroll and leave stack. The injection makes the code *look* guarded. (§B.8)
- **13 of 24 submodules cannot be enforced at all** — not in the `switch`. (§B.5)
- **No Symfony voters/roles**; `getRoles()` returns `['ROLE_USER']` for everyone. (§B.2)
- **No ownership/IDOR checks anywhere.** Confirmed IDOR:
  `/api/notifications/find-by-employee/{userId}`, `/api/employee/profile_photo_add/{empId}`,
  `/api/user/update/{id}`, `/api/notifications/find/{id}`, `/salary/adjustment/{id}`.

### H-5. 🔴 Secrets committed to version control (`.env`)

| Secret | Value / risk |
|---|---|
| `JWT_PASSPHRASE` | `fe5ddc…188e` — **private-key passphrase in git** |
| `MAILER_DSN` | `smtp://japarece@techrostrum.com:zhtlkdfcbnykqzfs@smtp.gmail.com:587` — **live Gmail app password** |
| `APP_SECRET` | `7cb0a6c38b8a731f436ba7174ffaadbe` |
| `DATABASE_URL` | `mysql://root:@127.0.0.1:3306/wchhris_live_test` — **`root` with an empty password** |
| commented `DATABASE_URL`s | **production/staging hosts + credentials**: `techrostrum-admin:Lap@121521@10.105.224.3` for `wchhris_live` and `wchhris_staging` — internal IP, real DB user, real password |

> 🔴 `.gitignore` excludes `/.env.local*` and `/config/jwt/*.pem` but **not `.env` itself**,
> which is tracked. The commented-out production DSNs are arguably worse than the active
> one: they hand an attacker the **internal IP, username and password of the live payroll
> database**.
> 🔴 **`APP_ENV=dev` and `APP_DEBUG=1`** are the committed defaults → if deployed as-is,
> the Symfony profiler and full stack traces are exposed.
> 🟠 `JWT_SECRET_KEY` / `JWT_PUBLIC_KEY` point at absolute paths on a **different machine's
> XAMPP install** (`F:/xampp/htdocs/Techrustrom/jwt/`) while the project runs under
> Laragon — the portable `%kernel.project_dir%/config/jwt/` form is commented out.

### H-6. 🔴 The dual-connection biometric sync

**Two distinct implementations exist; the "clean" one is dead code.**

**(a) `src/Service/SyncDatabaseConnection.php` — dead and broken.**
```php
class SyncDatabaseConnection extends Connection
{
    public function __construct(array $params, Driver $driver, Configuration $config, EventManager $eventManager)
    {
        parent::__construct($params, $driver, $config, $eventManager);   // connect to default DB
        $userDatabase = $this->fetchSyncDatabase();
        $params['dbname']   = $userDatabase['dbname'];
        $params['user']     = $userDatabase['user'];
        $params['password'] = $userDatabase['password'];
        parent::__construct($params, $driver, $config, $eventManager);   // reconnect
    }
    private function fetchSyncDatabase()
    { return $this->executeQuery('SELECT * FROM sync_connection')->fetchAssociative(); }
}
```
> 🔴 **Never registered.** `doctrine.yaml` declares no `wrapper_class`, and repo-wide the
> class name appears **only in its own file** — it is unreachable dead code.
> 🔴 **Would not work if enabled:** the entity column is **`username`**
> (`SyncConnection.php:19`), but the code reads **`$userDatabase['user']`** → undefined
> key → `null` user.
> 🔴 **`host` is never applied**, so it would reconnect to the *same* server with a
> different database name.
> 🔴 **Calling `parent::__construct()` twice** on a live `Connection` is an unsupported
> re-initialisation that leaks the first connection.
> 🔴 **`SELECT * FROM sync_connection` with `fetchAssociative()` silently takes whichever
> row MySQL returns first** — an implicit "there is exactly one row" assumption with no
> `WHERE`, no `ORDER BY`, no `LIMIT`.
> 🔴 **Connecting at construction time** means every request that touches DBAL would pay
> for a second DB handshake.

**(b) `SyncWorkerController` — the live path, raw `PDO`.**
```php
$dsn = sprintf('mysql:host=%s;dbname=%s;charset=utf8mb4', $connection['host'], $connection['dbname']);
$pdo = new PDO($dsn, $connection['username'], $connection['password']);
```
> 🔴🔴 **Reachable anonymously at `/sync/worker` with any HTTP method** (§H-1).
> 🔴 **Bypasses Doctrine entirely** — no connection pooling, no logging, no retry, no
> timeout. Raw `PDO` against a second production database from inside a web request.
> 🔴 `catch (\PDOException $e)` returns **`$e->getMessage()` to the client** (L52-53) —
> so an anonymous caller gets MySQL errors containing **host, database and username**.
> 🟠 Queries: `SELECT * FROM worker` (L59) is unbounded — the entire worker table streamed
> into memory. `syncWorkerLogsPerday` does `SELECT * FROM worker_logs ORDER BY login_date
> DESC LIMIT 1` then `WHERE login_date > :latestDate` — ✅ **correctly parameterised**
> (`bindParam`, `PDO::PARAM_STR`); no SQL injection found in the sync path.
> 🔴 `$result['login_date']` (L106) is used with **no null-check** — an empty
> `worker_logs` table fatals.
> 🟠 The whole sync runs **synchronously inside an HTTP request** with
> `flush()`/`clear()` every 10 rows — no queue, no lock. Two concurrent calls to the
> public endpoint will duplicate work and race.

**SQL injection assessment overall:** ✅ **No SQL injection was found.** All Doctrine
access uses QueryBuilder/DQL with `setParameter()`, and the only raw SQL (6 statements,
all in `SyncWorkerController` + the dead `SyncDatabaseConnection`) is either static or
properly bound.

### H-7. 🔴🔴 Employee PII committed to the public web root

```
public/excel_files/empfiles.csv   — 61,553 bytes, 182 rows × 31 columns, TRACKED IN GIT
```

> 🔴🔴 `public/` is the **document root** (`public/index.php` is the front controller).
> This file is therefore served as a **static asset at `https://<host>/excel_files/empfiles.csv`
> with no authentication of any kind** — Symfony's firewall never sees it.
> 182 employee records × 31 columns of HR data, downloadable by anyone who guesses the URL,
> and permanently present in git history.
> 🔴 The path is **hardcoded** in `SyncWorkerController::processCsv()` L349:
> `$this->getParameter('kernel.project_dir') . '/public/excel_files/empfiles.csv'`.

### H-8. 🟠 `CsvReader` — thin, unsafe, and used for identity matching

```php
class CsvReader {
    public function readCsv(string $filePath): array {
        $data = [];
        if (($handle = fopen($filePath, "r")) !== false) {
            while (($row = fgetcsv($handle, 1000, ",")) !== false) { $data[] = $row; }
            fclose($handle);
        }
        return $data;
    }
}
```
> 🟠 Registered `public: true` in `services.yaml` — the only service so marked.
> 🔴 **Fails silently.** A missing/unreadable file returns `[]`, so the sync reports
> success having matched nothing. No exception, no log.
> 🟠 **1000-byte line cap** — longer rows are split mid-record, silently corrupting data.
> 🟠 **Entire file loaded into memory** as a nested array; no streaming, no generator.
> 🟠 **No header handling** — consumers use **magic numeric indices**
> (`$row[5]` = first name, `$row[6]` = last name, `SyncWorkerController:355-356`). Any
> column reordering in the source spreadsheet silently mis-assigns identities.
> 🟠 **No encoding handling** (BOM/UTF-16 will corrupt the first field), no delimiter
> detection, no `filePath` validation → **path traversal** if a caller ever passes user input.
> 🔴 The matching itself is **fuzzy name comparison** (`compareNames()`/`splitName()`,
> L399-402) — employees are linked to biometric workers **by name string**, not by ID.
> Two "Dela Cruz, Juan"s will be conflated, attaching one person's attendance to another's payroll.
> 🟠 `processCsv()` **re-reads and re-parses the whole 61 KB CSV once per worker row**
> inside the `syncWorkers()` loop (L89 → L349-350) — O(n×m).

### H-9. 🔴 Plaintext passwords in the audit table

`AuditLog::addAuditLog()` stores `$request->getContent()` verbatim, and
`LoginController::login()` calls it on every login → `audit_trail_log.transactions`
accumulates `{"identifier":"…","password":"<PLAINTEXT>"}`. The table has **no read path
in the application at all** (§E.9). Pure liability.

### H-10. 🔴 All notification email routed to a hardcoded developer inbox

`->to($email)` commented out, `->to('lquisim@techrostrum.com')` hardcoded
(`NotificationService.php:162-163`). Every employee notification is both **undelivered**
and **leaked to one person**. Synchronous, unqueued, untried/uncaught, and inside a
per-recipient loop. See §E.5.

### H-11. 🟠 Hardcoded values

| Value | Location | Problem |
|---|---|---|
| `"SUR"` | `ManpowerController.php:173`, `:271` | Magic role code for **all** auto-provisioned employees |
| `'lquisim@techrostrum.com'` | `NotificationService.php:163` | Notification recipient |
| `'noreply@example.com'` | `NotificationService.php:161` | Placeholder sender domain |
| `'test'` | `LoginController.php:338` | `setUserId('test')` on every signup |
| `/public/excel_files/empfiles.csv` | `SyncWorkerController.php:349` | Hardcoded data path |
| `'Asia/Manila'` | ~12 sites | Timezone string repeated instead of centrally configured |
| `$row[5]`, `$row[6]` | `SyncWorkerController.php:355-356` | Magic CSV column indices |
| `notification_type` 0–4 | `NotificationService.php` | Magic ints, no enum, **inconsistent** (§E.3) |
| `$batchSize = 10` | `SyncWorkerController.php:60` | Magic batch size |

> ✅ No hardcoded **entity IDs** (`->find(1)` etc.) were found — the `SyncDatabaseConnection`
> comment *"Replace 1 with dynamic user ID if needed"* (L18) is a leftover referring to
> logic that no longer exists.

### H-12. 🟠 Information disclosure via exception messages

`return $this->json([... 'error' => $e->getMessage()])` is the standard error idiom
across `SuperAdminController` (5 sites), `UsersController` (4), `NotificationsController`,
`EmployeeRecordsController`, `SyncWorkerController`, and more.
`EmployeeRecordsController.php:284` is the worst: `"There's an error in code: ".$e`
**string-casts the whole exception object → full stack trace + absolute file paths**.
With `APP_DEBUG=1` (§H-5) this is amplified across the entire app.

### H-13. 🟠 Missing HTTP method restrictions

**17 routes declare no `methods:`** and therefore answer GET, POST, PUT, PATCH, DELETE
and HEAD identically. The dangerous ones:

| Route | Why it matters |
|---|---|
| `/api/user/update/{id}` | Account takeover via a **GET** URL (§B.12) |
| `/sync/worker` | Anonymous mass-write via GET |
| `/check/emp/dtr` | Anonymous via GET |
| `/api/dashboard` | Minor |
| `/api/permission` | Stub |
| `/signup` | Explicitly `['POST','GET']` — deliberate, and worse |

State-changing operations reachable by GET are trivially CSRF-able (no CSRF protection is
enabled — `framework.yaml` has `#csrf_protection: true` commented out), and get logged in
proxies, browser history and server access logs.

### H-14. 🟠 Data-integrity gaps

- **No DB unique constraints** on `EmployeeRecords.employee_code`, `EmployeeRecords.email`,
  `User.email`, `User.username`, or `UserType.user_code` — all uniqueness is
  check-then-insert in PHP, i.e. **racy**. Duplicates break
  `findOneByEmailOrUsernameOrPhone()` (`getOneOrNullResult()` → `NonUniqueResultException`)
  and permanently lock out login for the affected identifier.
- **Only 4 migrations** for a 60-entity schema → the database is **not** migration-managed;
  environments will have drifted.
- **`Types::ARRAY`** on 29 permission columns + `Shifts.days_of_week` — deprecated,
  unqueryable, and a PHP-object-injection surface (§B.6).
- **Free-text where enums belong:** `employee_status`, `position`, `employment_type`,
  `gender`, `civil_status`, `user_code`.
- **4 overlapping lifecycle flags on `User`** (`archived`, `removed`, `is_active`,
  `status`), 2 of them dead (§C.6).
- **Nullable booleans everywhere** → tri-state logic silently excludes legacy `NULL` rows
  from `archived = 0` filters (affects all 9 dashboard KPIs).
- **`age` denormalised** on `EmployeeRecords` and never recomputed.

### H-15. 🟠 Structural / maintainability

- **`ManpowerController` 125 KB** and **`ProjectController` 120 KB** — together 20% of the
  controller layer, each owning 5+ aggregate roots. `PayrollReportsController` 88 KB,
  `PayrollGenerationController` 58 KB, `EmployeePayrollProfileController` 45 KB.
- **Missing controllers** (`Department`, `Division`) with their logic buried in
  `ManpowerController`; **stub controller** (`Permission`); **triplicated** model
  controllers (§D.7).
- **Copy-paste duplication:** `LoginController::login()` and `revalidateSession()` share
  ~90 identical lines of permission-payload construction; the previous `login()`
  implementation sits commented out above it (L37-90). The whole `SubModules` payload
  block is written out **4 times** across `LoginController` and `SuperAdminController`.
- **Dead code:** `SyncDatabaseConnection` (whole class), `PermissionController`,
  `LoginController::createUsertype()`, unused imports of `AuditTrailLog` in
  `UserAccessValidation` and `NotificationService`, unused injected services in
  `DashboardController`/`SuperAdminController`/`PermissionController`, `User.status`,
  `User.loginCount`, ~40 commented-out `OneToMany` blocks in `User`.
- **Duplicate route name** `find_notification` (§E.6). `AccountabilityRecordsController`
  puts `name:` **and** `methods: ['DELETE']` on the **class-level** `#[Route]` (L14),
  making every child route name a concatenation like
  `delete_accountability_recordlist_accountability_records`.
- **Typos in the schema:** `DTRAdjutments` (entity + property), `$pasword`
  (`LoginController:470`), `'error1'`/`'error2'` response keys, `"credentials 5…12"` markers.
- **No tests.** No `tests/` directory, no `phpunit.xml`.
- **No `trusted_proxies`** → spoofable client IPs in the audit log.
- **CORS regex allows plain `http://`** and still whitelists `example.com`.

### H-16. Top 10 remediation priorities

| # | Action | Severity |
|---|---|---|
| 1 | Delete `/signup`, or move it under `/api` **and** hard-code a non-privileged role | 🔴🔴 |
| 2 | Stop returning the reset token from `/api/forget_password`; email it, use a random opaque token (not a JWT), and **enforce `token_expiry` in `resetPassword()`** | 🔴🔴 |
| 3 | Delete `/api/revalidate-session` or bind it to the authenticated principal | 🔴🔴 |
| 4 | Add ownership + role checks to `/api/user/update/{id}`; forbid self-service `user_type` changes; add `methods: ['PUT']` | 🔴🔴 |
| 5 | Move `/sync/worker`, `/check/emp/dtr`, `/salary/*`, `/tax_shield*` under `/api`; change the default access rule to `^/` = authenticated | 🔴🔴 |
| 6 | Delete `public/excel_files/empfiles.csv`, purge it from git history, rotate nothing-but-move the file outside the web root | 🔴🔴 |
| 7 | Rotate **every** secret in `.env` (JWT passphrase + keys, `APP_SECRET`, Gmail app password, all DB passwords); untrack `.env`; set `APP_ENV=prod`, `APP_DEBUG=0` | 🔴 |
| 8 | Stop logging raw request bodies — redact `password` in `AuditLog`; purge existing rows | 🔴 |
| 9 | Replace manual `validateUserAccess` calls with Symfony **Voters** + an `#[IsGranted]` attribute (or a kernel `controller` listener) so authorization is **opt-out, not opt-in**; add the 13 missing submodules; fix the phantom `getEmployeeProjects()` | 🔴 |
| 10 | Restore `->to($email)` in `NotificationService`, move mail to an async transport, wrap in try/catch; fix the swapped `projects`/`emp_project` arguments in `updateMainModules` | 🔴 |

---

## Appendix — file inventory

| File | Lines / Size | Verdict |
|---|---|---|
| `config/packages/security.yaml` | 2.9 KB | Prefix-only access control; no throttling |
| `config/packages/lexik_jwt_authentication.yaml` | 311 B | 24 h TTL |
| `.env` | 2.6 KB | 🔴 secrets committed |
| `src/Security/UserProvider.php` | 45 | ✅ correct and minimal |
| `src/Service/UserAccessValidation.php` | 123 | 🔴 11/24 submodules; 1 phantom; called on 13.6% of routes |
| `src/Service/JWTDecodedListener.php` | 19 | 🟠 near-no-op; 2 dead branches |
| `src/Service/AuditLog.php` | 45 | 🔴 logs plaintext passwords; write-only |
| `src/Service/NotificationService.php` | 168 | 🔴 hardcoded recipient; sync mail; type-code bugs |
| `src/Service/SyncDatabaseConnection.php` | 31 | 🔴 dead **and** broken (`user` vs `username`) |
| `src/Service/CsvReader.php` | 18 | 🟠 silent failure, 1000-byte cap, magic indices |
| `src/Controller/LoginController.php` | 503 | 🔴🔴 signup, reset, revalidate all broken |
| `src/Controller/UsersController.php` | 283 | 🔴🔴 unrestricted `updateUser` |
| `src/Controller/SuperAdminController.php` | 488 | 🔴🔴 no super-admin check; swapped-args bug |
| `src/Controller/PermissionController.php` | 43 | 🟠 empty stub |
| `src/Controller/EmployeeRecordsController.php` | 407 | 🔴 unvalidated attachments, IDOR |
| `src/Controller/ManpowerController.php` | 125 KB | 🔴 default password = email; 9 RBAC checks |
| `src/Controller/ProjectController.php` | 120 KB | 🟠 best RBAC coverage (21) but enormous |
| `src/Controller/BlocksController.php` | 2 routes | 🟠 read-only, no RBAC |
| `src/Controller/NotificationsController.php` | 163 | 🔴 IDOR + `findAll()` leak |
| `src/Controller/DashboardController.php` | 81 | 🟠 no RBAC, no scoping |
| `src/Controller/SyncWorkerController.php` | 19.7 KB | 🔴🔴 public raw-PDO sync |
| `src/Entity/EmployeeRecords.php` | 1,004 | Central master record |
| `src/Entity/SubModules.php` | 497 | 24 `Types::ARRAY` permission columns |
| `src/Entity/AuditTrailLog.php` | 82 | Write-only |
| `public/excel_files/empfiles.csv` | 61 KB / 182 rows | 🔴🔴 PII in web root, tracked in git |
| `migrations/` | 4 files | 🟠 schema not migration-managed |
| `tests/` | — | ❌ does not exist |
