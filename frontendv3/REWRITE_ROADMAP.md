# WCH HRIS — Frontend (frontendv3) Rewrite Roadmap (React)

> **Purpose.** Authoritative plan for rebuilding the WCH HRIS frontend as **React** (`frontendv3`). Read **cold, with no access** to the original Symfony/Twig project (`F:\laragon\www\wchhris`). It captures the design language, layout, navigation, component patterns, and the exact page/feature inventory that must be reproduced, and prescribes a clean React architecture.
>
> **Companion deep-dives:** `06-frontend-api-auth.md` (how the original talks to the API, auth/session, RBAC enforcement) and `07-frontend-design.md` (design language, layout shell, component patterns, dead boilerplate). This roadmap is self-contained for planning; those files hold the implementation detail.
>
> **Backend counterpart:** `backend/REWRITE_ROADMAP.md`.

---

## 0. TL;DR for the implementing agent

- **The original frontend is NOT React.** It is **Symfony 6 + Twig**, server-rendered, layered on the purchased **Tailwick Admin & Dashboard Template v1.1.0** (Themesdesign). We are rebuilding its *design and UX* in React; the backend API is the new FastAPI app.
- **~85% of the original Twig templates are unused vendor demo pages.** Do **not** port them. Port only the ~24 real HR routes/pages (inventory in §5).
- **Design tokens to reproduce:** brand primary = **`#3b82f6`** (Tailwind `blue`, named `custom-*` by Tailwick), dark surfaces = the `zink-*` ramp (`zink-800` page `#0f1824`, `zink-700` cards `#132337`), font = **Public Sans**, icons = **Lucide**. Light = slate-100 canvas, white cards; Dark = navy-inverted.
- **The new frontend already exists as a scaffold:** `frontendv3/` is the **Shadcn Admin Dashboard** (Vite + React + Tailwind + shadcn/ui + TanStack Router/Query/Table). Extend it — it already provides sidebar, theming (light/dark), and the component primitives we need.
- **Tech swaps (mechanical):** List.js → TanStack Table; Tailwick `data-modal-target` → shadcn `Dialog`; Flatpickr → `react-day-picker`; Choices.js → shadcn `Select`; Toastify → `sonner`; native + SweetAlert2 confirm → shadcn `AlertDialog` + `useMutation` toasts; vanilla validation → `react-hook-form` + `zod`; `permission.js` → a `useCan(module, action)` hook.
- **Carry forward the permission-driven UI** (menu items and action buttons appear/disappear by `can_view/can_add/can_edit/can_delete`). This is a core product behavior, not decoration.
- **Decide the API contract early** with the backend roadmap: the new API uses **JWT Bearer**; the React app calls it directly from the browser (the original mixed server-side proxy + direct JS — do NOT replicate the server-side proxy; go SPA-direct with an api client + codegen).

---

## 1. What the original frontend actually is

| Aspect | Detail |
|---|---|
| Stack | PHP 8.x, **Symfony 6**, **Twig** server-rendered HTML |
| Base template | **Tailwick Admin & Dashboard Template v1.1.0** (purchased), heavily customized |
| CSS | **Tailwind** (compiled `tailwind2.css` 660 KB; **no `tailwind.config.js` committed** — theme tokens live only in compiled CSS; must be re-declared in the new `tailwind.config`) |
| JS libs (real pages) | **List.js** (tables), **Flatpickr** (date/time), **Choices.js** (selects), **Toastify** (toasts), **SweetAlert2** (confirm dialogs), **Lucide** (icons), **SimpleBar** (scroll), **Tippy.js** (tooltips), **Popper**, **ApexCharts** (dashboard counters/charts), **Vanilla Calendar Pro** (mostly dead) |
| JS libs shipped but unused | jQuery DataTables, Prism.js, Swiper, scroll-hint, FullCalendar (dead include) |
| Charts | ApexCharts (dashboard KPI tiles + any charts) |
| Fonts | **Public Sans** (Google Fonts) |
| Icons | **Lucide** (primary) + Remix Icon (residual) |
| Build | Webpack Encore (do **not** replicate — use Vite) |
| Auth to API | Mixed: Symfony controllers proxy some calls server-side; Twig pages also `fetch()` the API directly from the browser with a JWT stored in Symfony **file session** (plaintext — insecure; the new app must use httpOnly cookie or secure token storage). |

**Key architectural decision:** The rewrite is a true SPA. The browser holds a JWT (access + refresh) and calls the FastAPI backend directly. There is **no** Symfony middle tier. (See `06-frontend-api-auth.md` for the original's split architecture and its weaknesses — public sync endpoints, CSRF exposure on 25 routes, plaintext JWT in file sessions — none of which should carry forward.)

---

## 2. Target tech stack (recommended)

Reuse `frontendv3/` (Shadcn Admin Dashboard):

- **Vite + React 18/19 + TypeScript** (strict).
- **Tailwind CSS v4** with a committed `tailwind.config` (the original lacked one — create it and bake in the tokens from §3).
- **shadcn/ui** primitives (Button, Input, Dialog, Select, Table, Tabs, Dropdown, Card, Badge, Calendar, Sonner toasts, AlertDialog). Do not hand-roll; add via the shadcn CLI.
- **TanStack Router** (file-based) — matches the scaffold.
- **TanStack Query** for server state; **Zustand** or React context for auth/session + UI prefs (theme, sidebar size).
- **TanStack Table** for all data grids (replaces List.js).
- **react-hook-form + zod** for forms/validation.
- **@hey-api/openapi-ts** for a typed API client generated from the FastAPI OpenAPI spec (already configured in the repo). This removes the ad-hoc `fetch` glue.
- **ApexCharts** (or Recharts) for the dashboard KPIs.
- **lucide-react** for icons (1:1 with the original Lucide usage).
- **react-day-picker** for date pickers; **react-dropzone** for file uploads.

---

## 3. Design language to reproduce (carry the look)

> Verbatim tokens extracted from the original's compiled CSS so the React app matches pixel-for-pixel.

### 3.1 Brand / primary — `custom-*`
Tailwick's `custom-*` scale is set to Tailwind **blue**:
| Token | RGB | Hex | Use |
|---|---|---|---|
| `custom-500` | `rgb(59 130 246)` | **`#3b82f6`** | primary brand (buttons, active sidebar, links) |
| `custom-600` | `rgb(37 99 235)` | `#2563eb` | hover/active |
| `custom-800` | — | `#1e40af` | shadow color |

A secondary brand accent appears in the app title: **`#002a45`** (deep navy, light mode) / `#ffff` (dark). Use only for the logo wordmark.

### 3.2 Dark-mode surface ramp — `zink-*` (desaturated blue-grey)
| Token | Hex | Use |
|---|---|---|
| `zink-100` | `#c8d7e9` | body text |
| `zink-200` | `#92afd3` | muted text / placeholders |
| `zink-500` | `#233a57` | table/input borders |
| `zink-600` | `#1c2e45` | raised surfaces / dropdowns / hover rows |
| `zink-700` | `#132337` | **card background (dark)** |
| `zink-800` | `#0f1824` | **page background (dark)** |
| `zink-900` | `#070c12` | bordered skin / deepest |

### 3.3 Light surfaces
- Page canvas: `slate-100` (`#f1f5f9`). Sidebar rule: `#e2e8f0`. Sidebar sub-item text: `slate-400`. Active sidebar item: blue (`custom-500`) text/bg.
- Cards: white, `rounded-md`, 1px `slate-200` border, `dark:bg-zink-700 dark:border-zink-600`, padding `1.25rem`.

### 3.4 Typography & spacing
- Font: **Public Sans** (`font-public` on `<body>`), weights 200–700.
- Base size 14px (`text-base` on body). Sidebar nav item 14px.
- Stock Tailwind 0.25rem spacing + template-added named spacings: `spacing.header` = 4.375rem (70px topbar), `spacing.vertical-menu` = 16.25rem (260px sidebar), `vertical-menu-md`/`vertical-menu-sm`, `max-w-boxed`, `min-h-sm`.
- Radius: `rounded-md` standard, `rounded-sm` for collapsed-sidebar flyouts.
- Shadow: `shadow-slate-500/10` (flyouts/modals), `dark:shadow-zink-600/20`.

### 3.5 Overall look
Conventional dense corporate SaaS admin: light slate canvas, white sticky topbar, 260px blue-accented left sidebar, data-heavy tables, blue primary buttons, 14px Public Sans. Dark mode is a fully-wired navy-inverted theme (used but secondary). **Reproduce both light and dark with a theme toggle.**

### 3.6 Theme config to add to the new Tailwind
Define `custom` (blue) and `zink` color ramps in `tailwind.config`, a `fontFamily.sans = ['Public Sans', ...]`, `fontSize` 14px base, and the named spacings above. Import Public Sans via `@fontsource/public-sans` (avoid the runtime Google Fonts fetch).

---

## 4. Layout & navigation to reproduce

### 4.1 Layout shell
- **App shell** = sticky **left sidebar** (260px, collapsible to icon-only / hidden on mobile drawer) + **topbar** (70px: mobile hamburger, search, notifications bell, theme toggle, user avatar dropdown) + **content area** + **footer**.
- Skin state machine via `<html data-*>` attributes in the original (`data-layout`, `data-sidebar`, `data-skin`, `data-sidebar-size`). In React: model these as theme/UI state (e.g. `useUiStore`): sidebar size (lg/md/sm/hidden), skin (default/bordered), topbar color. Persist to `localStorage`.
- **Topbar:** global search (command palette), notification bell → notification panel, theme (light/dark) toggle, user dropdown (profile, logout).
- **Notification area:** a slide-in panel listing in-app notifications (from the API). Original used `_notification-area.html.twig` + `NotificationListener`; reproduce with a query-backed drawer.

### 4.2 Real navigation tree (LABELS ARE VERBATIM — reproduce exactly)
```
Menu (section)
├ Dashboard                         [monitor-dot]     /dashboards-hr
├ Projects                          [cog]             /project/project
│   (guard: project.can_view AND project not empty)
├ Human Resource                    [circuit-board]  (collapsible)
│   ├ Daily Time Records            → /manpower/daily-time-records
│   └ Employees                     → /manpower/employee
├ Administration                    [user-round-cog]  (collapsible)
│   ├ Division                      → /management/division
│   ├ Department                    → /management/department
│   ├ Subdivisions                  → /project/subdivisions
│   ├ Phase                         → /project/phase
│   ├ Owner                         → /administration/owner
│   ├ Models & Facilities          → /administration/models
│   ├ Model Types                   → /administration/model-types
│   ├ Employee Settings             → /administration/user-settings
│   ├ Shifts                        → /administration/shifts
│   └ Roles and Access             → /super/user-roles   (guard: SADM/ADM)
├ Payroll Administration            [user-round-cog]  (collapsible)
│   ├ SSS Configuration            → /sss/config
│   ├ Pag-Ibig Configuration        → /pagibig/config
│   ├ BIR Configuration             → /bir/config
│   ├ Philhealth Configuration      → /philhealth/config
│   ├ Payroll                       → /employee-payroll
│   ├ Payroll Reports               → /payroll-reports
│   └ Overtime Request             → /overtime/request
├ Leave Administration              [user-round-cog]  (collapsible)
│   ├ Leave Policy                  → /leave-policy/
│   ├ Employee Leaves               → /employee-leaves/
│   ├ Holiday Configuration         → /holidays/
│   ├ Leave Request                 → /leave-request/
│   └ Leave Calendar                → /leave-request/calendar
└ Super Administration              [wrench]          (collapsible, guard: SADM)
    └ ALPMC Sync                    → /super/admin
```
**Outside the sidebar (deep links/buttons):** employee profile, employee projects, manpower, generate payslip, employee payroll profile, the subdivision wizard (`subwizard`), login, logout, forget/reset password, employee201 form.

**Permission guards** (reproduce): each collapsible section and most items show only when the user's `main_module_access.<module>.can_view` is true; `Roles and Access` and `Super Administration` additionally require `userTypeCode` `SADM`/`ADM`. The React sidebar must consume the permission payload from `/api/me` (or the login response) and conditionally render — use a `useCan()` hook backed by the same RBAC model the backend enforces (see backend roadmap §3.6).

### 4.3 Sidebar item anatomy (what `<NavItem>` must reproduce)
- Top-level link: `rounded-md`, 14px, blue hover/active (`custom-500`), py-2.5, icon + label; collapsible groups have a chevron that rotates.
- Active route highlight (use the router's active state, not JS `initActiveMenu()`).
- Mobile: overlay + drawer.

---

## 5. Page inventory — WHAT TO BUILD (used pages only)

> These ~24 routes are the real product. Everything else in the original `templates/` is dead vendor demo (charts-apex-*, apps-mailbox, apps-ecommerce-*, maps-*, apps-calendar, etc.) — **ignore**.

| # | Page | Route | Core UI |
|---|---|---|---|
| 1 | **Login** | `/login` | Email/username/contact + password; "forgot password" link |
| 2 | **Forgot / Reset password** | `/forget_password`, `/reset_password` | email → token → new password (token via email, not response body) |
| 3 | **Dashboard** | `/dashboards-hr` | 10 KPI link-tiles in 3 groups (HR / Project Mgmt / Admin), animated counters, Lucide icons, each tile links to its module |
| 4 | **Employee Masterlist** | `/manpower/employee` | Table: Code·Name·Email·Cell·Division·Department·Position·Employment Type·Date Hired·Action; search, filters, **Import CSV**, Add; server-side pagination; row → profile |
| 5 | **Employee Profile** | `/employee_profile/{id}` | tabbed: personal, employment, projects, leave, OT, accountability, attachments; edit modals |
| 6 | **Daily Time Records** | `/manpower/daily-time-records` | per-employee DTR table (login/out, rendered, OT, late, undertime, absence); filters by cutoff/employee; adjustments |
| 7 | **Division** | `/management/division` | table + add/edit/delete modals; Division Head = employee select |
| 8 | **Department** | `/management/department` | table + modals; Division + Department Head |
| 9 | **Subdivisions** | `/project/subdivisions` | table + modals |
| 10 | **Phase** | `/project/phase` | table + modals |
| 11 | **Owner** | `/administration/owner` | table + modals (property owners) |
| 12 | **Models & Facilities** | `/administration/models` | table + modals |
| 13 | **Model Types** | `/administration/model-types` | table + modals |
| 14 | **Employee Settings** | `/administration/user-settings` | employee reference/settings |
| 15 | **Shifts** | `/administration/shifts` | shift defs (start/end/lunch/days) + assignment |
| 16 | **Roles and Access** | `/super/user-roles` | RBAC editor: modules × can_view/add/edit/delete per role |
| 17 | **SSS Config** | `/sss/config` | contribution bracket editor |
| 18 | **Pag-IBIG Config** | `/pagibig/config` | contribution editor |
| 19 | **BIR Config** | `/bir/config` | tax bracket editor |
| 20 | **PhilHealth Config** | `/philhealth/config` | premium editor |
| 21 | **Payroll** | `/employee-payroll` | generate payroll for cutoff/employee; payslip view; YTD |
| 22 | **Payroll Reports** | `/payroll-reports` | filters + report tables (JSON/export) |
| 23 | **Overtime Request** | `/overtime/request` | list/create/approve OT requests |
| 24 | **Leave Policy** | `/leave-policy/` | leave type definitions + entitlements |
| 25 | **Employee Leaves** | `/employee-leaves/` | per-employee leave balances ledger |
| 26 | **Holiday Configuration** | `/holidays/` | holiday templates + yearly instances |
| 27 | **Leave Request** | `/leave-request/` | file/approve leave; status pills |
| 28 | **Leave Calendar** | `/leave-request/calendar` | monthly calendar of leaves/holidays |
| 29 | **ALPMC Sync** | `/super/admin` | biometric/worker sync trigger (super-admin) |
| 30 | **Subdivision Wizard** | `/subwizard` | multi-step subdivision creation |
| 31 | **Manpower / Employee Projects** | `/manpower`, `/employee-projects` | project assignment to employees |

(Numbers 1–3, 21–28, 30 are the highest-value; 4–20 are CRUD tables with the same pattern.)

---

## 6. Component patterns to reproduce (and their React equivalents)

| Original (Tailwick/Twig) | React (frontendv3) |
|---|---|
| **Tables = List.js** (DOM search/paginate) | **TanStack Table** (sorting, filtering, server pagination, column defs). Wrap in a `<DataTable>` component with the card chrome from §3.5. |
| **Modals = `data-modal-target`** (custom `common.js`) | shadcn **`Dialog`** (or `Sheet` for drawers). One `<Modal>` wrapper; pass title/footer. |
| **Date/time = Flatpickr** | **`react-day-picker`** (+ a time input). Keep `Y-m-d` / `H:i` display formats. |
| **Selects = Choices.js** | shadcn **`Select`** (or `Command` combo-box for searchable, e.g. Division Head). |
| **Toasts = Toastify** | **`sonner`** toasts via TanStack Query `onSuccess/onError`. |
| **Confirms = SweetAlert2** | shadcn **`AlertDialog`** (delete confirmations). |
| **Validation = native + ad hoc** | **`react-hook-form` + `zod`**; shared `zod` schemas mirror backend DTOs. |
| **Permission gating = `permission.js` + `view-*` classes** | **`useCan(module, action)`** hook + `<Can>` component; sidebar + buttons consume it. |
| **Tooltips = Tippy.js** | shadcn **`Tooltip`** (Radix). |
| **Scroll = SimpleBar** | native `overflow` / `radix-scroll-area` (optional). |
| **Charts = ApexCharts** | **ApexCharts (react)** or Recharts for dashboard KPIs. |
| **File upload = Dropzone** | **`react-dropzone`** (employee attachments, CSV import). |
| **Icons = Lucide (class)** | **`lucide-react`** (1:1). |

**Recurring page composition (template every CRUD page from these):**
1. Page title + breadcrumb bar.
2. Toolbar: search input, filter `Select`s, primary "Add" `Button` (permission-gated).
3. `<DataTable>` card with row actions (view/edit/delete, permission-gated).
4. Add/Edit `Dialog` (react-hook-form + zod). Delete `AlertDialog`.
5. Toast feedback; TanStack Query invalidation on mutation.

---

## 7. Auth & data flow (target)

- **Login:** POST credentials to FastAPI `/auth/login` → store access token (memory/state) + refresh token (httpOnly cookie set by backend, or encrypted localStorage). Attach access token as `Authorization: Bearer` via the generated api client interceptor.
- **Session:** on load, call `/auth/me` (or read login payload) to get user + `userTypeCode` + `main_module_access` permission map; store in an auth context/store. Drive sidebar + `useCan` from this.
- **Logout:** call backend logout (revoke refresh), clear state.
- **Password reset:** request → email with link containing signed token → reset form posts token + new password. **Token must NOT appear in any API response body** (original bug — do not replicate).
- **No server-side proxy:** the SPA calls the API directly. Configure CORS on the backend for the frontend origin. No CSRF needed for Bearer JWT, but protect against XSS (no plaintext token in DOM-accessible storage).
- **Generated client:** use `@hey-api/openapi-ts` against the FastAPI OpenAPI spec so every endpoint is typed; wrap with TanStack Query hooks (`useEmployees`, `useGeneratePayroll`, etc.).

---

## 8. Phased milestones

**Phase 0 — Scaffold & design tokens (1 wk)**
- Confirm `frontendv3` Shadcn base. Add `tailwind.config` tokens (`custom`=blue, `zink` ramp, Public Sans, named spacings). Theme toggle (light/dark). Sidebar shell + topbar + notification drawer wired to UI store.

**Phase 1 — Auth & shell (1 wk)**
- Login / forgot / reset pages. Auth context, token storage, api-client interceptor, `/auth/me`, `useCan` + `<Can>`, permission-driven sidebar rendering (§4.2). Logout.

**Phase 2 — CRUD foundation (2 wks)**
- `<DataTable>`, `<Modal>`, form primitives, toast/confirm wrappers. First CRUD pages (Division, Department, Shifts, Employee Settings) to lock the pattern. Employee masterlist + profile + CSV import.

**Phase 3 — Org / Projects / RBAC (1–2 wks)**
- Subdivisions, Phase, Owner, Models, Model Types, Employee Projects, Manpower, Subdivision Wizard. Roles & Access editor (RBAC UI).

**Phase 4 — Attendance / Leave / Holidays (2 wks)**
- Daily Time Records (DTR table + adjustments), Overtime Request (create/approve), Leave Request + Leave Calendar, Leave Policy, Employee Leaves ledger, Holiday Config. Wire permission guards.

**Phase 5 — Payroll & Config (2 wks)** ⚠ depends on backend Phase 4
- SSS/Pag-IBIG/BIR/PhilHealth config editors; Payroll generation + payslip + YTD; Payroll Reports. ALPMC Sync page (super-admin).

**Phase 6 — Dashboard & polish (1 wk)**
- Dashboard KPI tiles (ApexCharts/Recharts) + animated counters; breadcrumbs; empty/loading/error states; responsive pass; a11y pass.

**Phase 7 — Cutover**
- Point the api client at the new FastAPI; parity check key flows (login, generate payroll, file leave) against the old system; remove dead boilerplate; retire the Symfony frontend.

---

## 9. Open decisions to confirm with the product owner

1. Keep the **Tailwick look exactly** (blue `custom-500`, `zink-*` dark) or refresh the brand color? **(Recommend keep — familiarity.)**
2. Charting lib: ApexCharts (matches original) vs Recharts (more React-idiomatic)? 
3. Sidebar behavior defaults: expanded (lg) on desktop, hidden drawer on mobile — confirm.
4. Does the "ALPMC Sync" page stay (same biometric vendor) or become a generic import?
5. Dashboard KPI set: keep the original 10 tiles, or redefine?
6. Employee CSV import format: match the original 31-column `empfiles.csv` schema, or define a cleaner import contract?

---

## 10. Success criteria

- Visual parity with the original in light **and** dark mode (token match in §3).
- 100% of the ~24 real routes built; zero dead demo pages ported.
- Permission-driven sidebar + action buttons behave identically to the original (verified against a SADM vs a limited user).
- Auth uses Bearer JWT via typed generated client; no plaintext token in DOM storage; no token in reset-response body.
- Every CRUD page uses the shared `<DataTable>`/`<Modal>`/form/toast pattern (no one-off glue).
- Consumes the FastAPI OpenAPI spec via codegen; no hand-written fetch glue for core endpoints.
