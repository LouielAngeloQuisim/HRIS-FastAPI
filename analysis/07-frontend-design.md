# 07 — Frontend Design & UI Analysis
**Project:** WCH HRIS (`/mnt/f/laragon/www/wchhris`) — Symfony 6 + Twig, server-rendered
**Scope:** Design language, layout shell, component patterns, page inventory, styling/build pipeline, dead boilerplate
**Purpose:** Reference spec for a React (Vite + Tailwind) rewrite
**Mode:** READ-ONLY exploration — nothing in the source tree was modified.

---

## 0. Executive Orientation

The HRIS frontend is **not** a SPA. It is a classic Symfony/Twig server-rendered
application layered on top of a **purchased commercial Tailwind admin template**.
Almost every page is a full page load; interactivity is delivered by **jQuery +
vanilla JS + a grab-bag of vendor plugins**, and data mutations happen either by
native `<form method="POST">` posts to Symfony controllers, or by `$.ajax` calls
through a thin `assets/js/api.js` wrapper that talks to a **separate REST API
backend** (a second Symfony/Python service on another host/port).

Two consequences drive everything in this document:

1. **The look is entirely template-derived.** There is no bespoke design system.
   Recreating the visual identity means recreating *Tailwick's* token set.
2. **~85% of the Twig templates in `templates/` are unused vendor demo pages.**
   A rewrite that naively ports "all templates" would waste enormous effort.
   Section 6 enumerates exactly what is dead.

### 0.1 Template origin — CONFIRMED

The template is **Tailwick – Admin & Dashboard Template v1.1.0 by Themesdesign**
(not Mannat / not Domiex). Confirmed from three independent file headers:

`public/assets/scss/tailwind.scss` (lines 1–8):
```scss
/*
Template Name: Tailwick - Admin & Dashboard Template
Author: Themesdesign
Version: 1.1.0
Website: https://themesdesign.in/
Contact: Themesdesign@gmail.com
File: tailwind scss File
*/
```

Same header block appears verbatim in:
- `public/assets/scss/icons.scss` — "File: Icons scss File"
- `public/assets/js/layout.js` — "File: Layout Js File"
- `public/assets/js/app.js` — "File: Main Js File"
- `public/assets/js/tailwick.bundle.js` — "File: Common Plugins Js File"

Additional corroborating fingerprints left in the code:
- `templates/partials/_title-meta.html.twig` still emits
  `<title><?= $title ?> | Tailwick - Admin & Dashboard Template</title>`
- `templates/partials/_topbar.html.twig` cart drawer hard-codes the demo coupon
  `Discount <span>(TAILWICK50)</span>`
- Every layout partial carries `<meta content="Themesdesign" name="author">`

The company skin applied over Tailwick is **WRLD Capital Holdings** (logo assets
`wrld_icon_2.png`, `wrld_complete.png`, `wrld_white_complete2.png`,
`wrld_icon_2-removebg.png`), footer credit *"© WRLD Capital Holdings / Powered by
Techrostrum"*, and the product name **"Online Human Resource Information System"**.

---

## 1. Design Language / Visual Identity

### 1.1 Where the theme actually lives

There is **no `tailwind.config.js` in the project**. Verified:

```
$ find . -name "tailwind.config*" -not -path "./vendor/*"
./public/assets/libs/tailwindcss/stubs/tailwind.config.cjs   <- npm package stub only
./public/assets/libs/tailwindcss/stubs/tailwind.config.js    <- npm package stub only
./public/assets/libs/tailwindcss/stubs/tailwind.config.ts    <- npm package stub only
```

The Tailwind theme config that produced the design tokens was **not committed** —
only the compiled artefact `public/assets/css/tailwind2.css` (660 KB, the file
actually loaded) and its predecessor `tailwind.css` (552 KB, orphaned) exist.
**For a rewrite, the token values below were reverse-engineered directly out of
the compiled CSS** and are authoritative.

### 1.2 Brand / primary colour — `custom-*`

Tailwick's primary accent scale is named `custom-*`. In this build it is set to
**Tailwind's stock `blue`** palette. Extracted from `tailwind2.css`:

| Token | RGB | Hex |
|---|---|---|
| `custom-50`  | `rgb(239 246 255)` | `#eff6ff` |
| `custom-100` | `rgb(219 234 254)` | `#dbeafe` |
| `custom-200` | `rgb(191 219 254)` | `#bfdbfe` |
| `custom-300` | `rgb(147 197 253)` | `#93c5fd` |
| `custom-400` | `rgb(96 165 250)`  | `#60a5fa` |
| **`custom-500`** | **`rgb(59 130 246)`** | **`#3b82f6`** ← primary brand |
| `custom-600` | `rgb(37 99 235)`   | `#2563eb` ← primary hover/active |
| `custom-800` | `rgb(30 64 175)`   | `#1e40af` |
| `custom-900` | `rgb(30 58 138)`   | `#1e3a8a` |

Sampled literal declarations:
```css
.bg-custom-500{--tw-bg-opacity:1;background-color:rgb(59 130 246 / var(--tw-bg-opacity))}
.text-custom-600{--tw-text-opacity:1;color:rgb(37 99 235 / var(--tw-text-opacity))}
.border-custom-500{--tw-border-opacity:1;border-color:rgb(59 130 246 / var(--tw-border-opacity))}
.fill-custom-400{fill:#60a5fa}
.shadow-custom-800{--tw-shadow-color:#1e40af;--tw-shadow:var(--tw-shadow-colored)}
.to-custom-800{--tw-gradient-to:#1e40af var(--tw-gradient-to-position)}
```

The page loader (`public/assets/css/page-loader.css`) hard-codes a near-identical
blue: `radial-gradient(farthest-side,#3b8cf6 94%,#0000)`.

One hard-coded corporate navy appears inline in `_topbar.html.twig`:
`<h6 style="color: #002a45;">Online Human Resource Information System</h6>`
(and its dark-mode twin `color: #ffff`). **`#002a45` is the only non-Tailwind
brand colour in the shell.**

### 1.3 Dark-mode surface scale — `zink-*`

Tailwick names its dark neutral ramp `zink-*` (a desaturated blue-grey, *not*
Tailwind's `zinc`). Extracted:

| Token | RGB | Hex | Typical use |
|---|---|---|---|
| `zink-50`  | (light text in dark mode) | — | hover text |
| `zink-100` | `rgb(200 215 233)` | `#c8d7e9` | primary body text (dark) |
| `zink-200` | `rgb(146 175 211)` | `#92afd3` | muted text / placeholders (dark) |
| `zink-300` | `rgb(88 133 188)`  | `#5885bc` | disabled text |
| `zink-400` | `rgb(57 95 142)`   | `#395f8e` | borders/checkbox fill |
| `zink-500` | `rgb(35 58 87)`    | `#233a57` | table & input borders |
| `zink-600` | `rgb(28 46 69)`    | `#1c2e45` | raised surfaces / dropdowns / hover rows |
| `zink-700` | `rgb(19 35 55)`    | `#132337` | **card background (dark)** |
| `zink-800` | `rgb(15 24 36)`    | `#0f1824` | **page background (dark)** |
| `zink-900` | `rgb(7 12 18)`     | `#070c12` | deepest / bordered-skin |

### 1.4 Light-mode surfaces & semantic layout tokens

| Token | Value | Meaning |
|---|---|---|
| `bg-body-bg` | `rgb(241 245 249)` = `#f1f5f9` (slate-100) | app page background |
| `text-body`  | `rgb(30 41 59)` = `#1e293b` (slate-800) | default body text |
| `bg-topbar`  | `rgb(255 255 255)` = `#ffffff` | topbar background |
| `border-topbar-border` | `rgb(226 232 240)` = `#e2e8f0` | topbar bottom rule |
| `border-vertical-menu-border` | `rgb(226 232 240)` = `#e2e8f0` | sidebar rule |
| `text-topbar-item` | `rgb(51 65 85)` = `#334155` (slate-700) | topbar icon buttons |
| `text-vertical-menu-sub-item` | `rgb(148 163 184)` = `#94a3b8` (slate-400) | sidebar sub-item |
| `w-vertical-menu` | `16.25rem` (260 px) | expanded sidebar width |
| `h-header` / `spacing.header` | `4.375rem` (70 px) | topbar height |
| `text-vertical-menu-item-font-size` | `.875rem` (14 px) | sidebar nav item size |

Semantic status colours are **plain stock Tailwind palettes** used directly
throughout pages: `green-*` (success/approved/active), `red-*` (danger/reject/
delete), `yellow-*`/`orange-*` (pending/warning), `sky-*`/`blue-*` (info),
`purple-*`, `slate-*` (neutral/muted). There is no custom `success`/`danger`
alias — a rewrite should keep using raw Tailwind palette names.

The shipped Theme Customizer drawer (`partials/_customizer.html.twig`) exposes
**no accent-colour picker** — the blue `custom-*` scale is fixed at build time.
It only offers: Layout (Vertical / Horizontal / Semi Dark), Skin (Default /
Bordered), Light & Dark mode, LTR / RTL, Content Width (Fluid / Boxed), Sidebar
Size (Default / Compact / Small-Icon), Navigation Type (Sticky / Scroll /
Bordered / Hidden), 4 Sidebar Colors and 3 Topbar Colors (light / dark / brand /
modern).

### 1.5 Typography

Single web font, loaded from Google Fonts:

`public/assets/scss/fonts/fonts.scss`
```scss
@import url('https://fonts.googleapis.com/css2?family=Public+Sans:wght@200;300;400;500;600;700&display=swap');
```

- **Family:** **Public Sans** (utility class `font-public`, applied on `<body>`).
- **Weights shipped:** 200, 300, 400, 500, 600, 700.
- **Base size:** `text-base` on `<body>`; the template adds non-standard numeric
  size utilities used pervasively in pages — `text-15`, `text-16`, `text-17`,
  `text-19`, `text-20`… (e.g. page titles use `text-16`, card titles `text-15`).
- **Icon fonts / icon sets — three coexist:**
  1. **Remix Icon** (`remixicon.woff2`, `.ri-*` classes, plus `font-remix`
     pseudo-element glyphs such as `content-['\ea6e']` for the sidebar chevron
     and `content-['\ea54']` for the breadcrumb separator) — `assets/css/icons.css`.
  2. **Lucide** (`assets/libs/lucide/umd/lucide.js`, `<i data-lucide="bell-ring">`)
     — the dominant icon system in the shell and HR pages.
  3. Inline SVG in a few dashboard/report widgets.

### 1.6 Spacing, radius, elevation

- Stock Tailwind 0.25rem spacing scale, plus template-added named spacings:
  `spacing.header` (4.375rem), `spacing.vertical-menu` (16.25rem),
  `vertical-menu-md`, `vertical-menu-sm`, `max-w-boxed`, `min-h-sm`.
- **Radius:** `rounded-md` is the default everywhere (cards, buttons, inputs,
  dropdowns, avatars); `rounded-full` for pills/badges/avatars;
  `rounded-sm`/`rounded-b-sm` for collapsed-sidebar flyouts.
- **Elevation:** near-flat. The compiled `.card` rule is
  ```css
  .card{margin-bottom:1.25rem;border-radius:.375rem;border-width:1px;
        border-color:rgb(226 232 240);background-color:rgb(255 255 255);
        --tw-shadow-color:#f1f5f9;--tw-shadow:var(--tw-shadow-colored)}
  .card-body{padding:1.25rem}
  ```
  i.e. **`rounded-md` + 1px `#e2e8f0` border + an almost-invisible `#f1f5f9`
  tinted shadow + 20px padding + 20px bottom margin**. Real shadows are reserved
  for floating layers: `shadow-md` (dropdowns), `shadow-lg` +
  `shadow-slate-500/10` (sidebar flyouts, modals), `dark:shadow-zink-600/20`.
- **Card canon** (repeated verbatim on ~every HR page):
  ```html
  <div class="card">
    <div class="card-body">
      <h6 class="mb-4 text-15">Title</h6>
      ...
    </div>
  </div>
  ```
  `.card` / `.card-body` are Tailwick component classes baked into
  `tailwind2.css` (white bg, `rounded-md`, 1px slate-200 border,
  `dark:bg-zink-700 dark:border-zink-600`; `.card-body` = `padding:1.25rem`).

### 1.7 Overall look

Conventional, dense, "corporate SaaS admin": **light slate-100 canvas, white
bordered cards, a 260 px white left sidebar with blue active states, a 70 px
white sticky topbar, blue primary buttons, 14 px Public Sans**. Data-heavy —
most screens are a filter bar + a wide table + modals. Dark mode is a true
inverted navy theme (`zink-800` page / `zink-700` cards), fully wired but rarely
exercised by the HR pages' bespoke markup (several custom pages hard-code
`bg-white`/`text-slate-*` without a `dark:` counterpart, so dark mode is
**partially broken on custom pages** — a rewrite should fix or drop it).

---

## 2. Layout & Navigation

### 2.1 The layout shell — file-by-file

Two root layouts exist in `templates/partials/`:

| File | Lines | Role |
|---|---|---|
| `base.html.twig` | 72 | **The app shell** — sidebar + topbar + content + footer. Extended by every authenticated page. |
| `without-nav.html.twig` | 37 | **Chromeless shell** — head + `{% block content %}` + scripts, no nav. Used by auth/error screens. |

`base.html.twig` composition order (verbatim structure):

```twig
{% include 'partials/_main.html.twig' %}          {# <!DOCTYPE html><html …data-*> #}
  <head>
    <title>{% block title %}Welcome{% endblock %} | Online Human Resource Information System</title>
    <meta content="Minimal Admin & Dashboard Template" name="description">
    <meta content="Themesdesign" name="author">
    <link rel="shortcut icon" href="{{ asset('assets/images/wrld_icon_2-removebg.png') }}">
    {% block stylesheets %}<style>.hidden{display:none}.disabled{pointer-events:none;opacity:.5}</style>{% endblock %}
    {% include 'partials/_head-css.html.twig' %}
  </head>
{% include 'partials/_body.html.twig' %}          {# <body class="…" data-user-permissions data-user-sub-permission> #}
  {% block body %}
  <div class="group-data-[sidebar-size=sm]:min-h-sm …">
      {% include 'partials/_menu.html.twig' %}    {# = _topbar + _sidebar #}
      <div id="page-loader" class="flex min-h-screen …"><div class="pw-loader"></div></div>
      <div id="content-wrapper" class="relative min-h-screen hidden">
          {% include 'partials/_page-wrapper.html.twig' %}   {# opens the offset content <div> #}
              <div class="container-fluid group-data-[content=boxed]:max-w-boxed mx-auto">
                  {% block content %}{% endblock %}
              </div>
          </div>
          {% include 'partials/_footer.html.twig' %}
      </div>
  </div>
  {% include 'partials/_customizer.html.twig' %}
  {% include 'partials/_vendor-scripts.html.twig' %}
  {% block javascripts %}{% endblock %}
  {% endblock %}
</body>
{{ errorScript|default('')|raw }}
</html>
```

Notes a rewrite must know:

- **`_page-wrapper.html.twig` opens a `<div>` that `base.html.twig` closes.**
  It is an *unbalanced* partial — a classic Twig-template smell. Its single
  giant class string is the entire responsive offset math:
  `group-data-[sidebar-size=lg]:ltr:md:ml-vertical-menu … pt-[calc(theme('spacing.header')*1)] pb-[calc(theme('spacing.header')*0.8)] px-4 …`
- **`page-loader` / `content-wrapper` FOUC guard:** the whole app renders
  `hidden`, with a CSS bar loader visible until `DOMContentLoaded`, at which
  point `assets/js/app.js` does
  `document.getElementById("page-loader").style.display="none";
   document.getElementById("content-wrapper").classList.remove("hidden");`
  → In React this is unnecessary; drop it (or replace with a Suspense boundary).
- **`errorScript|raw`** is injected *after* `</body>` — controllers can push an
  arbitrary `<script>` string into the page. A rewrite must replace this with a
  proper toast/error state.

### 2.2 Root `<html>` data-attribute state machine

`partials/_main.html.twig` is one line and defines the whole layout state:

```html
<!DOCTYPE html>
<html lang="en" class="light scroll-smooth group"
      data-layout="horizontal" data-sidebar="light" data-sidebar-size="lg"
      data-mode="light" data-topbar="light" data-skin="default"
      data-navbar="sticky" data-content="fluid" dir="ltr">
```

Every responsive/skin variation in the CSS is expressed as a Tailwind
`group-data-[…]:` variant off these attributes (`group` is on `<html>`).
Persistence: `assets/js/layout.js` (loaded first, in `_head-css`) restores the
attributes from `sessionStorage` before paint to prevent a flash.

> ⚠️ **Note the default is `data-layout="horizontal"`**, yet the app ships and is
> used as a **vertical left sidebar**. `sessionStorage` (set by the customizer)
> overrides it in practice, and `applyScrollbarLogic()`/`initActiveMenu()` in
> `app.js` only run their sidebar branch when `data-layout == "vertical"`.
> A rewrite should simply hard-code the vertical layout.

### 2.3 `<body>` — permission payload

```twig
<body class="text-base bg-body-bg text-body font-public dark:text-zink-100 dark:bg-zink-800
             group-data-[skin=bordered]:bg-body-bordered group-data-[skin=bordered]:dark:bg-zink-700"
      data-user-permissions="{{ app.session.get('main_module_access')|json_encode }}"
      data-user-sub-permission="{{ app.session.get('sub_module_access')|json_encode }}">
```

The **entire RBAC matrix is serialised into two body data-attributes** and
applied client-side by `assets/js/permission.js` on `DOMContentLoaded` — see
§3.13.

### 2.4 Topbar (`_topbar.html.twig`, 287 lines)

Left → right:

1. **Logo block** — 4 `<img>` variants swapped by CSS for
   light/dark × expanded/collapsed: `wrld_complete.png`,
   `wrld_icon_2-removebg.png`, `wrld_white_complete2.png`.
2. **`#topnav-hamburger-icon`** button — `chevrons-left` / `chevrons-right`
   Lucide icons; toggles sidebar size / mobile drawer.
3. **Search input** — `<input placeholder="Search for ...">`. **Cosmetic only** —
   no handler is bound anywhere.
4. **App title** — two `<h6>`s (light: inline `color:#002a45`; dark: `color:#ffff`)
   reading *"Online Human Resource Information System"*.
5. **`#light-dark-mode`** button (Lucide `sun`) — dark/light toggle.
6. **Notification bell** — `{% include 'partials/_notification-area.html.twig' %}`.
7. **`#customizerButton`** (Lucide `settings`) — opens the Theme Customizer drawer.
8. **User avatar dropdown** (`#dropdownMenuButton`) — shows
   `app.session.get('profile_image_path')` (fallback
   `assets/images/users/user-dummy-img.jpg`), header "Welcome to HRIS",
   `app.session.get('fullname')` + `app.session.get('userTypeName')`, then:
   - **Profile** → `path('employee_profile', {employee_code: session.empCode})`
     (falls back to `#` when `empCode` is empty)
   - **Sign Out** → `path('logout')`
   (Inbox / Chat / Upgrade-Pro items are commented out.)

**Dead code inside `_topbar.html.twig`:** a 9-language flag dropdown (commented
out) and a fully rendered **e-commerce "Shopping Cart" side drawer**
(`#cartSidePenal`, lines ~161–285) with 3 hard-coded demo products, a
`TECHROSTRUM50` coupon banner, a `$2,531.17` total, and "Continue Shopping" /
"Checkout" links to `apps-ecommerce-*`. **It is still in the DOM of every
authenticated page.** Do not port it.

### 2.5 Notification area (`_notification-area.html.twig`, 74 lines)

- Bell button with an animated unread dot
  (`animate-ping bg-sky-400` over `bg-sky-500`).
- Dropdown panel `min-w-[20rem] lg:min-w-[26rem]`, scroll-capped by
  **simplebar**: `<div data-simplebar class="max-h-[350px]">`.
- Rendered **server-side from the session**:
  `{% set notifications = app.session.get('notification_message') %}` then
  `{% for notification in notifications %}` printing
  `<b>{{ notification.sender_fullname }}</b> {{ notification.action }}`, the
  timestamp as `{{ notification.datetime|date('l h:i A') }}` with a Lucide
  `clock` icon, and a hand-rolled Twig "time ago" (`diff.y/m/d/h/i/s`).
- Empty state: `<p>No notifications available.</p>`.
- **No polling / websocket.** Notifications only refresh on full page load.
  A React rewrite should move this to a `/api/notifications` poll or SSE.

### 2.6 Sidebar (`_sidebar.html.twig`) — 1 080 lines / **866 KB**

Verified: `wc -l templates/partials/_sidebar.html.twig` → **1080**.
The 866 KB is *entirely* Tailwind class strings — each `<a>` carries a ~2 500
character class attribute encoding all sidebar/topbar/layout skin permutations.
Stripping `class="…"` collapses the file to 54 KB.

Structure:

```
<div class="app-menu …">
  ├── logo <a href="{{path('dashboard')}}"> ×2  (light / dark variants)
  ├── <button id="vertical-hover">            (pin/unpin the compact sidebar)
  └── <div id="scrollbar">                    (SimpleBar mount point)
        └── <ul id="navbar-nav"> … menu items … </ul>
</div>
<div id="sidebar-overlay"></div>              (mobile backdrop)
```

**Is it static HTML or generated? → STATIC, hand-authored HTML**, with Twig
`{% if %}` guards for permissions and `{{ path('route_name') }}` for hrefs.
There is **no menu-builder service, no YAML/PHP menu tree, no Knp Menu**.
Adding a page means hand-editing this 866 KB file.

#### 2.6.1 THE ACTUAL LIVE MENU TREE

Everything outside the block below is inside `{# … #}` Twig comments. This is
the complete real navigation (labels verbatim, with Lucide icon + Symfony route):

```
┌ "Menu"                                                         (section label)
│
├ Dashboard                          [monitor-dot]   → path('dashboard')          /dashboards-hr
│
├ Projects                           [cog]           → path('project')            /project/project
│   guard: main_module_access.project.can_view is true  AND  .project is not empty
│
├ Human Resource                     [circuit-board] (collapsible)
│   guard: main_module_access.humanres.can_view is true
│   ├ Daily Time Records                             → path('app_attendance')     /manpower/daily-time-records
│   └ Employees                                      → path('app_employee')       /manpower/employee
│
├ Administration                     [user-round-cog] (collapsible)
│   guard: main_module_access.administration.can_view is true
│   ├ Division                                       → path('division')           /management/division
│   ├ Department                                     → path('department')         /management/department
│   ├ Subdivisions                                   → path('subdivision')        /project/subdivisions
│   ├ Phase                                          → path('phase')              /project/phase
│   ├ Owner                                          → path('view_owner')         /administration/owner
│   ├ Models & Facilities                            → path('view_models')        /administration/models
│   ├ Model Types                                    → path('adm_model_types')    /administration/model-types
│   ├ Employee Settings                              → path('adm_user_settings')  /administration/user-settings
│   ├ Shifts                                         → path('adm_shifts')         /administration/shifts
│   └ Roles and Access                               → path('super_roles')        /super/user-roles
│         guard: userTypeCode == 'SADM' or 'ADM'
│   (Category → path('category') is present but COMMENTED OUT)
│
├ Payroll Administration             [user-round-cog] (collapsible)
│   guard: main_module_access.payroll.can_view is true
│   ├ SSS Configuration                              → path('app_sss_config')            /sss/config
│   ├ Pag-Ibig Configuration                         → path('app_pagibig_config')        /pagibig/config
│   ├ BIR Configuration                              → path('app_bir_config')            /bir/config
│   ├ Philhealth Configuration                       → path('app_phil_health_config')    /philhealth/config
│   ├ Payroll                                        → path('view_employee_payroll')     /employee-payroll
│   ├ Payroll Reports                                → path('app_payroll_reports')       /payroll-reports
│   └ Overtime Request                               → path('app_overtime_request')      /overtime/request
│   (Employee's Payroll + Employee Payroll Profile links are COMMENTED OUT)
│
├ Leave Administration               [user-round-cog] (collapsible)
│   guard: main_module_access.emp_leaves.can_view is true
│   ├ Leave Policy                                   → path('app_leave_policy')      /leave-policy/
│   ├ Employee Leaves                                → path('app_employee_leaves')   /employee-leaves/
│   ├ Holiday Configuration                          → path('app_holiday')           /holidays/
│   ├ Leave Request                                  → path('app_leave_request')     /leave-request/
│   └ Leave Calendar                                 → path('app_leave_calendar')    /leave-request/calendar
│
└ Super Administration               [wrench]        (collapsible)
    guard: app.session.get('userTypeCode') == 'SADM'
    └ ALPMC Sync                                     → path('super_sync')            /super/admin
```

**Reachable only outside the sidebar** (deep links / buttons / topbar):
`employee_profile`, `app_emp_projects`, `app_emp_project_id`, `app_manpower`,
`generate_payslip`, `app_employee_payroll_profile`, `subwizard`, `login`,
`logout`, `forget_password`, `reset_password`, `employee201_form`.

#### 2.6.2 Sidebar item anatomy (what a React `<NavItem>` must reproduce)

- **Top-level link:** `relative dropdown-button flex items-center ltr:pl-3
  ltr:pr-5 mx-3 my-1 group/menu-link text-vertical-menu-item-font-size
  font-normal rounded-md py-2.5 transition-all duration-150 ease-linear`
  + `text-vertical-menu-item hover:text-vertical-menu-item-hover
  hover:bg-vertical-menu-item-bg-hover
  [&.active]:text-vertical-menu-item-active [&.active]:bg-vertical-menu-item-bg-active`
- **Chevron:** a Remix-icon pseudo-element, rotated by the `.show` class —
  `[&.dropdown-button]:before:content-['\ea6e']` (chevron-down) flipping to
  `[&.dropdown-button]:[&.show]:before:content-['\ea4e']` (chevron-up),
  `before:font-remix ltr:before:right-2`.
- **Sub-item:** `relative flex items-center px-6 py-2` with a 4 px bullet drawn
  as `before:absolute ltr:before:left-1.5 before:top-4 before:w-1 before:h-1
  before:rounded before:bg-vertical-menu-sub-item`, turning
  `[&.active]:before:bg-vertical-menu-sub-item-active`.
- **Sub-menu container:** `.dropdown-content`, `hidden` by default; when the
  sidebar is collapsed (`data-sidebar-size=sm`) it becomes an absolutely
  positioned flyout `group-data-[sidebar-size=sm]:group-hover/sub:block
  ltr:left-full shadow-lg shadow-slate-700/5`.
- Each `<a>` also carries a **`data-key="t-…"` i18n key** (e.g. `data-key="t-division"`).
  A JSON-based translation layer exists (`public/assets/lang/*`, `app.js`
  `setLanguage()/getLanguage()`), but the language switcher is commented out of
  the topbar → **i18n is effectively dormant**; keys are also frequently wrong
  (many Payroll-Administration items reuse `data-key="t-product"`).

#### 2.6.3 Active-route highlighting

Pure client-side, in `public/assets/js/app.js` → `initActiveMenu()`:

```js
var currentPath = window.location.pathname;
var a = document.getElementById("navbar-nav").querySelector('[href="' + currentPath + '"]');
if (a) {
    a.classList.add("active");
    var parentCollapseDiv = a.parentElement.parentElement.parentElement;
    if (parentCollapseDiv) {
        if (document.documentElement.getAttribute("data-layout") == "vertical")
            parentCollapseDiv.classList.remove("hidden");         // open the group
        parentCollapseDiv.classList.add("active");
        parentCollapseDiv.previousElementSibling?.classList.add("active");
        parentCollapseDiv.previousElementSibling?.classList.add("show");  // rotate chevron
        …
    }
}
initMenuItemScroll();   // auto-scrolls SimpleBar so the active item is centred
```

Characteristics / gotchas to fix in a rewrite:
- **Exact `pathname` string match only.** No prefix matching → detail routes
  (`/employee/profile/{code}`, `/manpower/attendance/{id}/{code}`) never
  highlight anything, and query strings break it.
- It walks exactly three `parentElement` hops — fragile to markup changes.
- It also runs on `window.load` *and* after SimpleBar init, and in
  `data-sidebar-size=sm` mode re-injects the cached `navbarMenuHTML` after a
  500 ms `setTimeout` before re-running.
- React equivalent: `<NavLink end={false}>` + `useMatch`/`matchPath` with prefix
  matching, and derive `open` state for the parent group declaratively.

#### 2.6.4 Mobile responsiveness

- Breakpoint logic is Tailwind's `md:` (768 px) applied via
  `group-data-[sidebar-size=lg]:ltr:md:ml-vertical-menu` on the content wrapper
  and `ltr:md:left-vertical-menu` on the footer — i.e. **below `md` the content
  has no left offset and the sidebar becomes an overlay drawer**.
- `#topnav-hamburger-icon` → `toggleHamburgerMenu()` in `app.js`, which flips
  `data-sidebar-size` between `lg`/`sm`/`md` on desktop and shows
  `#sidebar-overlay` (a full-screen backdrop `<div>`) on mobile.
- `windowResizeHover()` re-evaluates on `resize`.
- Sidebar sizes: **`lg`** = 16.25 rem full, **`md`** = compact (icon + label
  stacked, centred), **`sm`** = 56-ish px icon rail with hover flyouts.
- Tables are made mobile-usable with **`overflow-x-auto`** wrappers and the
  **scroll-hint** plugin (`.js-scrollable`) rather than responsive stacking.

#### 2.6.5 Dark / light toggle

`app.js` → `lightDarkMode()`:

```js
document.getElementById('light-dark-mode').addEventListener('click', () => {
  if (sessionStorage.getItem("data-mode") === "light") {
      setAttrItemAndTag("data-mode",   "dark");
      setAttrItemAndTag("data-sidebar","dark");
      setAttrItemAndTag("data-topbar", "dark");
      updateActiveBtn("sidebarColorTwo"); updateActiveBtn("topbarColorTwo"); updateActiveBtn("dataModeTwo");
  } else {
      setAttrItemAndTag("data-mode",   "light");
      setAttrItemAndTag("data-sidebar","light");
      setAttrItemAndTag("data-topbar", "light");
      updateActiveBtn("sidebarColorOne"); updateActiveBtn("topbarColorOne"); updateActiveBtn("dataModeOne");
  }
});
function setAttrItemAndTag(attr, val){
  document.documentElement.setAttribute(attr, val);
  sessionStorage.setItem(attr, val);
}
```

- One click flips **three** attributes at once (mode + sidebar + topbar).
- Persisted in **`sessionStorage`, not `localStorage`** → the choice is lost when
  the tab closes. Re-applied pre-paint by `assets/js/layout.js`.
- Tailwind's `dark:` variant keys off the `.dark` class that Tailwick's CSS
  couples to `data-mode` (`<html class="light …">` initially).
- **Caveat:** many *custom-written* HRIS pages omit `dark:` counterparts
  (hard-coded `bg-white`, `text-slate-700`, `border-slate-200`), so dark mode is
  visually broken on a meaningful subset of real pages.

### 2.7 Footer (`_footer.html.twig`, 17 lines)

Fixed to the bottom, offset by the sidebar width via the same
`ltr:md:left-vertical-menu` / `group-data-[sidebar-size=…]` variants,
`h-14 border-t py-3 px-4 dark:border-zink-600`, two-column grid:

- Left: `<script>document.write(new Date().getFullYear())</script> © WRLD Capital Holdings.`
- Right (`hidden lg:block`): `Powered by Techrostrum`

### 2.8 Page title / breadcrumb partials — BOTH BROKEN

`_page-title.html.twig` (14 lines) renders a title + breadcrumb with the Remix
chevron separator `before:content-['\ea54'] before:font-remix`, **but its body is
raw PHP short-echo tags inside a Twig file**:

```twig
<h5 class="text-16"><?= ($title) ? $title : '' ?></h5>
...
<a href="#!" class="text-slate-400 dark:text-zink-200"><?= ($pagetitle) ? $pagetitle : '' ?></a>
```

`<?= … ?>` is never evaluated by Twig → this partial can only ever emit empty
strings, and **it is not `include`d by `base.html.twig` at all**. Same problem in
`_title-meta.html.twig`.

**The working replacement is a Symfony UX Twig Component.**
`src/Components/Breadcrumb.php`:

```php
#[AsTwigComponent('breadcrumb')]
class Breadcrumb {
    public string $title = '';
    public string $pagetitle = '';
    public string $pageLink = '';
}
```

rendered by `templates/components/Breadcrumb.html.twig` (14 lines) — identical
markup to `_page-title` but with real Twig interpolation:

```twig
<div class="flex flex-col gap-2 py-4 md:flex-row md:items-center print:hidden">
  <div class="grow"><h5 class="text-16">{{ title }}</h5></div>
  <ul class="flex items-center gap-2 text-sm font-normal shrink-0">
    <li class="relative before:content-['\ea54'] before:font-remix … before:text-slate-400">
      <a href="{{ pageLink ? pageLink : '#' }}" class="text-slate-400 dark:text-zink-200">{{ pagetitle }}</a>
    </li>
    <li class="text-slate-700 dark:text-zink-100">{{ title }}</li>
  </ul>
</div>
```

Every real page opens `{% block content %}` with, e.g.:
`{{ component('breadcrumb', { pagetitle: 'Division', title: 'Division' }) }}`.
**154 templates call it** (real pages *and* demo pages).

**This is the single genuinely reusable component in the whole frontend.** A
React rewrite should model it as `<PageHeader title parent parentHref />` and
put it in the route layout instead of repeating it in every page body.
`_page-title.html.twig` and `_title-meta.html.twig` are dead — delete.

---

## 3. Component Patterns

### 3.0 Which JS libraries are actually shipped vs actually used

`public/assets/libs/` contains **38 vendor directories** (the full Tailwick
bundle). Only a fraction is referenced by the HRIS pages.

| Library | Purpose | Loaded globally? | Used by real HR pages? |
|---|---|---|---|
| **Tailwind CSS** (`libs/tailwindcss`) | utility CSS framework — source of `tailwind2.css` | compiled artefact only | ✅ everywhere |
| **Lucide** (`libs/lucide/umd/lucide.js`) | SVG icon set, `<i data-lucide="…">` | ✅ `_vendor-scripts` | ✅ everywhere |
| **Remix Icon** (`css/icons.css` + woff2) | icon font `.ri-*` + `font-remix` pseudo glyphs | ✅ `_head-css` | ✅ chevrons/breadcrumbs |
| **jQuery 3.7.1** (`js/jquery/jquery-3.7.1.min.js`) | DOM + `$.ajax` for all page scripts | ✅ `_vendor-scripts` | ✅ almost every page |
| **Popper.js** (`libs/@popperjs/core`) | positions `.dropdown-menu` | ✅ `_vendor-scripts` (+6 pages re-include) | ✅ all dropdowns |
| **Choices.js** (`libs/choices.js`) | searchable/tag `<select>` — attribute `data-choices` | ✅ CSS+JS in shell | ✅ **20 pages** |
| **Flatpickr** (`libs/flatpickr`) | date & time picker — `data-provider="flatpickr"` / `"timepickr"` | ✅ CSS+JS in shell (JS twice) | ✅ **14 date + 6 time** |
| **Toastify JS** (`libs/toastify-js/src/toastify.js`) | toast notifications | ✅ `_vendor-scripts` | ✅ **18 pages** |
| **SimpleBar** (`libs/simplebar`) | custom scrollbars (sidebar `#scrollbar`, notification list) | ✅ `_vendor-scripts` | ✅ shell only |
| **Tippy.js + Popper** (`libs/tippy.js/tippy-bundle.umd.min.js`) | tooltips (`data-tooltip`) | ✅ `_vendor-scripts` | ⚠️ shell-loaded; a handful of `data-tooltip` attrs (e.g. dashboard contact modal) |
| **Prism.js** (`libs/prismjs`) | code-sample syntax highlighting | ✅ `_vendor-scripts` | ❌ **demo pages only — dead weight on every page** |
| **List.js + List.Pagination.js** | client-side table search / sort / paginate | per page | ✅ **28 pages** — *the* table engine |
| **SweetAlert2** (`libs/sweetalert2`) | confirm dialogs | per page | ✅ 4 pages (user_settings, employees-payroll-profile, apps-employees, apps-manpower) |
| **FullCalendar** (`libs/fullcalendar/index.global.min.js`) | month calendar | per page | ✅ 1 page — Leave Calendar |
| **Vanilla Calendar Pro** (`libs/vanilla-calendar-pro`) | inline mini-calendar | per page | ⚠️ included by `dashboards-hr` but its widget is commented out → effectively dead |
| **ApexCharts** (`libs/apexcharts`) | charts | per page | ✅ 1 page — Employee Profile |
| **Dropzone** (`libs/dropzone`) | drag-drop uploads | per page | ✅ 1 page — Employee Profile (attachments) |
| **Grid.js** (`libs/gridjs` + `scss/plugins/_gridjs.scss`) | data grid | ❌ | ❌ **0 real pages** (theme override SCSS exists but is unused) |
| **jQuery DataTables** (`js/datatables/*` incl. buttons/jszip/pdfmake) | data grid + export | ❌ | ❌ **0 real pages** |
| **Select2** (`public/assets/select2/dist`) | select enhancement | ❌ | ❌ **0 references anywhere** — orphaned vendor drop |
| **Swiper** (`libs/swiper`) | carousels | ❌ | ❌ demo only |
| **Scroll Hint** (`libs/scroll-hint`) | "scrollable" hint on wide tables | ❌ | ❌ demo only |
| Leaflet / GMaps / leaflet-routing-machine | maps | ❌ | ❌ demo only |
| ECharts, funnel-graph-js | charts | ❌ | ❌ demo only |
| CKEditor 5 (`libs/@ckeditor`) | WYSIWYG | ❌ | ❌ demo only |
| Cleave.js, nouislider, multi.js, @simonwep (Pickr), cropperjs, glightbox, plyr, gsap, aos, draggable, moment, read-smore, clipboard | misc | ❌ | ❌ demo only |

**Bottom line for a React rewrite — only 9 libraries need real replacements:**
Lucide (→ `lucide-react`), Choices.js (→ `react-select`/Radix), Flatpickr
(→ `react-day-picker`), Toastify (→ `sonner`/`react-hot-toast`), List.js
(→ TanStack Table), SweetAlert2 (→ Radix AlertDialog), FullCalendar
(→ `@fullcalendar/react`), ApexCharts (→ `react-apexcharts`/Recharts),
Dropzone (→ `react-dropzone`). Everything else is dead weight.

### 3.1 Tables — **List.js**, not Grid.js and not DataTables

This is the single most important pattern. The canonical table
(`administration/division.html.twig` lines 29–93) is:

```html
<div class="card" id="divisionTable">                     <!-- List.js root -->
  <div class="card-body"><div class="flex items-center">
      <h6 class="text-15 grow">Divisions List</h6>
      <div class="shrink-0">
        <button data-modal-target="addDivisionModal" class="add-division text-white btn bg-custom-500 …">
          <i data-lucide="plus" class="inline-block size-4"></i> <span class="align-middle">Add Division</span>
        </button></div></div></div>

  <div class="!py-3.5 card-body border-y border-dashed border-slate-200 dark:border-zink-500">
    <form action="#!"><div class="grid grid-cols-1 gap-5 xl:grid-cols-12">
      <div class="relative xl:col-span-2">
        <input type="text" class="ltr:pl-8 search form-input …" placeholder="Search for code, name, description etc...">
        <i data-lucide="search" class="absolute ltr:left-2.5 top-2.5 size-4 …"></i>
      </div></div></form></div>

  <div class="card-body"><div class="-mx-5 -mb-5 overflow-x-auto">
    <table class="w-full border-separate table-custom border-spacing-y-1 whitespace-nowrap">
      <thead class="text-left">
        <tr class="relative rounded-md bg-slate-100 dark:bg-zink-600 … [&.active]:after:border-custom-500">
          <th class="px-3.5 py-2.5 first:pl-5 last:pr-5 font-semibold sort" data-sort="code">Code</th>
          …
          <th …>Action</th>
        </tr></thead>
      <tbody class="list">
        {% for division in divisions %}
        <tr class="relative rounded-md after:absolute ltr:after:border-l-2 … [&.active]:bg-slate-100">
          <td class="… id hidden">{{ division.id }}</td>
          <td class="… code">{{ division.code }}</td>
          …
          <td class="action-division …"> <!-- kebab dropdown --> </td>
        </tr>{% endfor %}
      </tbody></table>

    <div class="noresult" style="display:none">
      <div class="py-6 text-center">
        <i data-lucide="search" class="size-6 mx-auto text-sky-500 fill-sky-100"></i>
        <h5 class="mt-2">Sorry! No Result Found</h5>
        <p class="mb-0 text-slate-500 dark:text-zink-200">We've searched more than 199+ users …</p>
      </div></div>
  </div>

  <div class="flex flex-col items-center gap-4 px-4 mt-4 md:flex-row" id="pagination-element">
    <div class="grow"><p class="text-slate-500">Showing <b class="showing">10</b> of <b class="total-records">{{ divisions|length }}</b> Results</p></div>
    <div class="flex gap-2 pagination-wrap">
      <a class="… page-item pagination-prev" href="javascript:void(0)"><i data-lucide="chevron-left"></i> Prev</a>
      <ul class="flex flex-wrap items-center gap-2 pagination listjs-pagination"></ul>
      <a class="… page-item pagination-next" href="javascript:void(0)">Next <i data-lucide="chevron-right"></i></a>
    </div></div>
</div>
```

Wired in `{% block javascripts %}` by the template's own helper
(`public/assets/js/app.js:927`):

```js
function paginateTable (tableName = "", columnNames = [], displayLimit = 10) {
    let showing  = document.querySelector(".showing");
    let totalRec = document.querySelector(".total-records").innerHTML;
    displayLimit > totalRec ? showing.innerHTML = totalRec : showing.innerHTML = displayLimit;
    var options = { valueNames: columnNames, page: displayLimit ?? 10, pagination: true,
                    plugins: [ ListPagination({ left: 2, right: 2 }) ] };
    var table = new List(tableName, options).on("updated", function (list) { …noresult toggle, prev/next disabled, counters… });
}
// page usage:
var divisionColumnNames = ["code","name","description","divisionHead"];
paginateTable("divisionTable", divisionColumnNames, 10);
```

Contract the markup must honour (React rewrite must preserve the *behaviour*, not
these classes):
- Root element `id` = List.js container; `<tbody class="list">`; **each cell needs
  a class equal to its `valueNames` key** (`code`, `name`, …).
- Sortable header = `<th class="sort" data-sort="code">`.
- Search box = `<input class="search">`; empty state = `.noresult`.
- Counters = `.showing` / `.total-records`; page list = `ul.pagination.listjs-pagination`;
  `.pagination-prev` / `.pagination-next` with a `.disabled` class.
- Hidden ID column is smuggled as `<td class="id hidden">`.

**Three table strategies coexist** (a rewrite should unify on one):
1. **List.js client-side** — 28 pages (all reference lists / config tables).
   *Everything is rendered server-side, then paginated in the browser.* This is
   O(all rows) HTML for e.g. every employee — a real performance problem.
2. **Server-side pagination** — 3 pages only
   (`administration/user_settings`, `employee_payroll_profile/employees-payroll-profile`,
   `manpower/apps-employees`) using controller vars `currentPage`, `limit`,
   `totalPages`, `totalEmployees` with `?p=&l=` query params.
3. **Plain static `<table>`** — payslips, reports, some detail panels; no JS.

`table-custom` / `border-separate border-spacing-y-1` gives the signature look:
**row-gapped "floating rows"** with a header row on `bg-slate-100`, and a
2 px left accent bar on the active row (`[&.active]:after:border-custom-500`).

### 3.2 Modals — Tailwick's own `data-modal-target` (no Bootstrap JS)

Despite `bootstrap@5.3.2` being a `package.json` dependency, **no Bootstrap JS is
ever loaded**. Modals are implemented by `public/assets/js/common.js →
drawerSetting()`:

- Open: any element with `data-modal-target="modalId"`.
- Close: any element with `data-modal-close="modalId"`.
- A backdrop `<div id="backDropDiv" class="fixed inset-0 bg-gray-900/20 z-[1049] backdrop-overlay hidden">`
  is created once and appended to `<body>`; clicking it closes the open modal/drawer.
- Show/hide is a `hidden` + `show` class dance with a 200 ms (modal) / 0 ms
  (drawer) `setTimeout`, plus `body.classList.toggle('overflow-hidden')`.
- Same function powers **drawers** via `data-drawer-target` / `data-drawer-close`
  (used by the topbar Customizer, the dead cart panel, and 3 HR pages).

Modal markup canon:
```html
<div id="addDivisionModal" modal-center
     class="fixed flex flex-col hidden transition-all duration-300 ease-in-out left-2/4 z-drawer -translate-x-2/4 -translate-y-2/4 show">
  <div class="w-screen md:w-[30rem] bg-white shadow rounded-md dark:bg-zink-600">
    <div class="flex items-center justify-between p-4 border-b dark:border-zink-300/20">
      <h5 class="text-16">Add Division</h5>
      <button data-modal-close="addDivisionModal" class="text-slate-400 hover:text-red-500"><i data-lucide="x" class="size-5"></i></button>
    </div>
    <div class="max-h-[calc(theme('height.screen')_-_180px)] p-4 overflow-y-auto"> …form… </div>
  </div>
</div>
```
Sizes seen: `md:w-[25rem]` (confirm), `md:w-[30rem]` (standard form),
`md:w-[45rem]` / `md:w-[60rem]` (wide forms). `z-drawer` is a custom z-index token.

**⚠️ The single worst pattern in the codebase — per-row modal duplication.**
Edit and Delete modals are emitted *inside a Twig `{% for %}` over the whole
dataset*, giving one full modal DOM tree **per record**:
```twig
{% for division in divisions %}
  <div id="editDivisionModal{{division.id}}" …> … </div>
{% endfor %}
{% for division in divisions %}
  <div id="deleteModal{{division.id}}" …> … </div>
{% endfor %}
```
On a 1 000-employee list this is 2 000 hidden modals. **A React rewrite must
replace this with one modal instance driven by selected-row state.**

Modals used to be present in 34 of the real templates (`data-modal-target`).

### 3.3 Forms & validation

- **No form-validation library is used on real pages.** Validation is
  **native HTML5** (`required`, `type="email"`, `type="number"`, `min`/`max`) plus
  ad-hoc jQuery in the page's `<script>` block. Present in 33 templates.
  (`assets/js/pages/form-validation.init.js` exists and uses JustValidate-style
  logic, but is only referenced by the demo `employee201/forms-validation.html.twig`.)
- **Symfony Form component is NOT used** — every form is hand-written HTML posting
  to a controller route (`<form action="{{ path('submit_division') }}" method="post">`)
  with plain `name="…"` fields and `<input type="hidden">` for ids.
- **No CSRF tokens** are emitted on these hand-rolled forms.
- Field classes (memorise these three; they are on literally every input):
  - text: `form-input border-slate-200 dark:border-zink-500 focus:outline-none focus:border-custom-500 disabled:bg-slate-100 … dark:bg-zink-700 dark:focus:border-custom-800 placeholder:text-slate-400`
  - select: `form-select …` (same modifier chain)
  - checkbox: `form-checkbox` (rare), switches use `[&:checked]:bg-custom-500` patterns
- Label canon: `<label class="inline-block mb-2 text-base font-medium">Division Name</label>`
  followed by `<span class="text-red-500">*</span>` for required.
- Buttons: `btn` base class + colour chain, e.g. primary
  `text-white btn bg-custom-500 border-custom-500 hover:bg-custom-600 focus:ring focus:ring-custom-100 active:bg-custom-600`;
  danger swaps `custom`→`red`; ghost/cancel is `bg-white text-red-500 hover:bg-red-100 dark:bg-zink-600`.
- `assets/js/global_functions.js` adds two global helpers bound by class:
  `.reset-form` (clears the *nearest* form's inputs/textareas/checkboxes but
  deliberately **not** selects) and `.numbers-only`
  (`this.value = this.value.replace(/[^0-9]/g,'')`).

### 3.4 Selects — Choices.js

Attribute-driven: `<select class="form-select …" data-choices name="divisionHead">`.
Variants seen across pages: `data-choices`, `data-choices-search-false`,
`data-choices-multiple-remove-item-button`, `data-choices-removeItem`,
`data-choices-sorting-false`, `data-choices-groups`, `data-choices-text-unique-true`.
Initialised generically by `tailwick.bundle.js`. **20 real pages.**
Dynamically injected rows must be re-initialised manually (several pages do
`new Choices(el, {...})` inline after an AJAX row insert).

### 3.5 Date & time pickers — Flatpickr

```html
<input type="text" data-provider="flatpickr" data-date-format="Y-m-d"
       class="form-input …" placeholder="Select date">
<input type="text" data-provider="timepickr" data-time-basic="true" class="form-input …">
```
Supported attributes (parsed in `tailwick.bundle.js` and re-implemented in
`assets/js/global_functions.js` for dynamically-added nodes):
`data-date-format`, `data-enable-time`, `data-altFormat`, `data-minDate`,
`data-maxDate`, `data-default-date`, `data-multiple-date`, `data-range-date`,
`data-inline-date`, `data-disable-date`, `data-week-number`; timepickr:
`data-time-basic`, `data-time-hrs` (24 h), `data-min-time`, `data-max-time`,
`data-default-time`, `data-time-inline`.

`global_functions.js` exposes **`reinitializeFlatpickr()`** and
**`reinitializeTimepickr()`** which pages call after injecting new rows —
they guard with `if (!item._flatpickr)`. This is a strong signal of how much
dynamic row-adding the payroll/attendance screens do.

Note: **Flatpickr's `<script>` is included twice** in `_vendor-scripts.html.twig`.

### 3.6 Calendars

- **Leave Calendar** (`leave_request/apps-leave-calendar.html.twig`) uses
  **FullCalendar** global build (`libs/fullcalendar/index.global.min.js`).
- `dashboards-hr` loads **vanilla-calendar-pro** but its widget block is
  commented out → dead include.

### 3.7 Tabs

`common.js → tabsComponents()`, markup-driven:
```html
<ul class="nav-tabs …">
  <li class="active"><a data-tab-toggle data-target="overviewTab" href="#!">Overview</a></li>
</ul>
<div><div id="overviewTab" class="tab-pane block">…</div><div id="docsTab" class="tab-pane hidden">…</div></div>
```
Toggles `.active` on the `<li>` and `hidden`/`block` on `.tab-pane`.
Used by only **3 real pages**: Employee Profile (its main navigation),
Holidays, and the Subdivision Wizard.

### 3.8 Collapse / accordion

`common.js → collapseComponent()`: `.collapsible` > `.collapsible-header`
(gets `.show`) + `.collapsible-content` (toggles `hidden`). 4 real pages.

### 3.9 Dropdowns (kebab menus, filters, user menu)

`common.js → dropdownEvent()` + **Popper.js**:
```html
<div class="relative dropdown">
  <button class="dropdown-toggle btn …" data-bs-toggle="dropdown"><i data-lucide="more-horizontal" class="size-3"></i></button>
  <ul class="absolute z-50 hidden py-2 mt-1 list-none bg-white rounded-md shadow-md dropdown-menu min-w-[10rem] dark:bg-zink-600">
    <li><a class="edit-division block px-4 py-1.5 text-base text-slate-600 dropdown-item hover:bg-slate-100 …"
           data-modal-target="editDivisionModal{{division.id}}" href="#!">
        <i data-lucide="file-edit" class="inline-block size-3 ltr:mr-1"></i><span class="align-middle">Edit</span></a></li>
    <li><a class="delete-division …" data-modal-target="deleteModal{{division.id}}" href="#!">
        <i data-lucide="trash-2" …></i><span class="align-middle">Delete</span></a></li>
  </ul>
</div>
```
- The `data-bs-toggle="dropdown"` attribute is a **Bootstrap leftover; it does
  nothing** — the handler binds to `.dropdown-toggle`.
- Auto-close behaviour via `data-tw-auto-close="inside|outside"`; a global
  `window` click handler calls `dismissDropdownMenu()`.
- 31 real pages. The row-action kebab (Edit / Delete, sometimes View / Approve /
  Reject / Print) is the universal table action pattern.

### 3.10 Toasts / alerts — Toastify JS

Two idioms coexist:

**(a) Flash-message bridge** (most common). The controller sets a Symfony flash;
the template emits a hidden marker and a jQuery block reads it:
```twig
{% for flash_message in app.flashes('status') %}
  <div class="hidden" id="status" data-status="{{ flash_message }}"></div>
{% endfor %}
```
```js
if (status.length) {
  if (status.data('status') == 'success') {
     Toastify({ newWindow:true, text:'Division added successfully', gravity:'top',
                position:'right', className:'bg-green-500', stopOnFocus:true,
                offset:{x:0,y:0}, duration:3000, close:true }).showToast();
  } else { Toastify({ …text:'Division not added, something went wrong.', className:'bg-red-500'… }).showToast(); }
}
```
Colour convention: `className: "bg-green-500"` success / `"bg-red-500"` error;
always top-right, 3 s, dismissible.

**(b) `showToast(message, className)`** — the shared helper in
`public/assets/js/api.js`, called automatically on every failed `$.ajax`.

**Confirmations:** mostly a bespoke *delete modal* (centred card, `delete.png`
illustration, "Are you sure?" / "Are you certain you want to delete this record?",
Cancel + red "Yes, Delete It!"). **SweetAlert2** is used for confirms on only 4
pages. There is also a `[data-toast]` declarative API in `tailwick.bundle.js`
(`data-toast-text`, `-gravity`, `-position`, `-className`, …) used by demo pages.

### 3.11 Badges / status pills

No component class — raw Tailwind, e.g.
`px-2.5 py-0.5 text-xs font-medium rounded border bg-green-100 border-transparent text-green-500 dark:bg-green-500/20`.
Colour convention observed across Leave / Overtime / Attendance / Payroll:
- **green** = Approved / Active / Present / Paid
- **red** = Rejected / Inactive / Absent / Cancelled
- **yellow / orange** = Pending / For Approval / Late
- **sky / blue** = Info / Processing / Draft
- **purple** = special leave types
- **slate** = N/A / Archived

### 3.12 File upload

- **Employee Profile** (attachments tab) is the only page with a real uploader:
  **Dropzone** (`libs/dropzone/dropzone-min.js`) posting to
  `path('upload_attachment')`; allowed extensions enforced server-side
  (`csv, pdf, doc, docx, jpg, jpeg, png`, 25 MB default cap); files land in
  `uploads/{employee_code}/`; download/delete via
  `path('download_attachment', …)` / `path('delete_attachment', …)`.
- Everything else is a plain `<input type="file">` (6 templates): profile
  picture (`upload_profile_picture`), Employee-201 CSV import
  (`import_emp201` / `import_csv`), DTR import (`import_dtr`), SSS/BIR table
  import (`app_sss_import_config`, `app_tax_import_config`).

### 3.13 Permission-driven UI (a pattern the rewrite MUST preserve)

`public/assets/js/permission.js` runs on `DOMContentLoaded`, reads
`document.body.dataset.userPermissions` / `.userSubPermission`, and **hides DOM
nodes by convention-based class name**:

```js
if (!canView)   hideOrModifyElements(`.view-${moduleName}`);
if (!canEdit)   hideOrModifyElements(`.edit-${moduleName}`);      // 'phase' → removes 'editable-cell' instead
if (!canAdd)    hideOrModifyElements(`.add-${moduleName}`);
if (!canDelete) hideOrModifyElements(`.delete-${moduleName}`);
if (!canEdit && !canAdd)    hideOrModifyElements(`.action-${moduleName}`);
if (!canEdit && !canDelete) hideOrModifyElements(`.action-${moduleName}`);
```

Main modules: `project`, `humanres`, `administration` (+`payroll`, `emp_leaves`
used in the sidebar guards).
Sub-modules (verbatim list): `daily_time_record`, `subdivision`, `division`,
`department`, `phase`, `owner`, `models`, `model_types`, `emp_settings`,
`shifts`, `projects`, `emp_project`, `emp_list`, `sss_config`, `pagibig_config`,
`bir_config`, `philhealth_config`, `payroll`, `payroll_reports`, `leave_policy`,
`emp_leaves`, `holiday_config`, `leave_request`, `leave_calendar`.
Special case: `.division-item` is hidden when `division.can_view` is false.

Hence every actionable element carries a marker class —
`class="add-division …"`, `class="edit-division …"`, `class="delete-division …"`,
`class="action-division …"`. **React equivalent:** a `usePermission(module)` hook
+ `<Can module="division" action="add">` guard component; do **not** port the
"render everything then hide it" approach (it leaks data and is trivially
bypassed with devtools).

### 3.14 Other shell behaviours worth noting

- **KPI counters**: `<span class="counter-value" data-target="{{ employees }}">0</span>`
  — `app.js` animates 0 → target on load.
- **Editable table cells**: `.editable-cell` (Phase module) — inline edit-in-place.
- **`{{ javascriptSnippet|default('')|raw }}`** and
  **`{{ errorScript|default('')|raw }}`** — controllers can inject arbitrary JS
  strings into pages. Replace with typed props/state in React.
- **Print**: `print:hidden` utilities on breadcrumb/footer; payslip & report
  pages rely on `window.print()`.
- **Excel export**: server-side (PhpSpreadsheet via `ExportXLSService`) — the
  UI is just a form/button hitting a `generate_*_report` route that streams a
  `.xlsx`.

---

## 4. Page Inventory — USED PAGES ONLY

Derived by cross-referencing every `$this->render(...)` in `src/Controller/*.php`
(21 controllers) with `templates/`. Result: **41 rendered templates that exist**
(+3 rendered but **missing** → fatal), **15 partials**, 1 Twig component, 1 email
template and 1 included modal fragment = **~59 live files**. Everything else is
boilerplate (§6).

Legend: **R** = Symfony route name · **U** = URL · **T** = template · lines verified with `wc -l`.

### 4.1 Auth & password (chromeless — `partials/without-nav.html.twig`)

| Page | R / U | T (lines) | Content | Components |
|---|---|---|---|---|
| **Login** | `login` `/login`; also `home` `/`, and `validate_login` `/validate_login` re-renders it on failure | `auth-login-boxed.html.twig` (141) | Centred boxed card, "Welcome!" heading, username + password, "Sign In" submit → `path('validate_login')`, "Forgot Password?" → `path('forget_password')`. `auth-login.init.js`. Vendor language dropdown (English/Spanish/German/French/Japanese/Italian/Russian/Arabic) still in markup. | plain form, HTML5 validation |
| **Forgot password** | `forget_password` `/forget_password` → posts `email_forget_password` | `forget_password/auth-reset-password-basic.html.twig` (86) | "Forgot Password?" — email field, submit, back-to-login | plain form |
| **Set new password** | `reset_password` `/reset_password/{token}` → posts `form_reset_password` | `forget_password/auth-create-password-basic.html.twig` (167) | Three states in one file: **Access Denied** (bad/expired token), **Reset Password**, **Set a New Password** (new + confirm) | plain form |
| **Reset success** | rendered by `form_reset_password` | `forget_password/auth-reset-password-success.html.twig` (72) | "Password Reset Successful" + link to login | static |
| **Logout** | `logout` `/auth-logout-boxed` | *(no template — invalidates session and redirects)* | — | — |
| **Reset e-mail body** | — | `emails/reset_password_link.html.twig` (9) | "Hello {{ employee }}… Click here!" `{{ resetUrl }}` | ⚠️ bizarrely `{% include 'partials/_head-css.html.twig' %}` inside an email |

### 4.2 Dashboard

| Page | R / U | T (lines) | Content | Components |
|---|---|---|---|---|
| **HR Dashboard** | `dashboard` `/dashboards-hr` (also served for `home` `/` when logged in) | `dashboards-hr.html.twig` (269) | **10 KPI link-tiles in 3 labelled groups.** *Human Resource*: Employee List (`employees`), Daily Time Records (`dtr_count`), Divisions, Departments. *Project Management*: Manpower Assignment (`manpower_count` → `project?t=pl#onGoingProjectsTable`), On-Going Projects, Subdivisions. *Administration*: Property Owners, User Administration, Facilities & Home Models. Each tile = Lucide icon + `<span class="counter-value" data-target="…">0</span>` animated counter + label, wrapped in an `<a>` to the module. | counter animation (`app.js`), `contactDetailsModal` (+ tippy `data-tooltip`), list.js loaded, vanilla-calendar loaded but the "Overall Employees" table + "Upcoming Scheduled" calendar blocks are **commented out** |

### 4.3 Human Resource — employees & DTR

| Page | R / U | T (lines) | Content | Components |
|---|---|---|---|---|
| **Employee Masterlist** | `app_employee` `/manpower/employee` | `manpower/apps-employees.html.twig` (736) | "Employee List" table: **Employee Code · Name · Email · Cellphone No. · Division · Department · Position · Employment Type · Date Hired · Action**. Toolbar: search, filter selects, **Import CSV**, **Add Employee**. Row click → `employee_profile`. | **server-side pagination** (`currentPage/limit/totalPages`), Choices, Flatpickr, SweetAlert2, Popper, `apps-hr-employee.init.js` + `pages-employees.js`; modals: `addEmployeeModal`, `editEmployeeModal`, `deleteModal`, `contactDetailsModal` |
| **Employee Profile (201 file)** | `employee_profile` `/employee/profile/{employee_code}` | `employee_profile/apps-employee-profile.html.twig` (**4 513** — the largest template) | Avatar header + **7 tabs** (`data-tab-toggle`): **Overview**, **Documents**, **Projects**, **Payroll**, **Leave Request**, **Daily Time Records**, **Overtime Request**, **Accountability Records**. *Overview* sections: Personal Information (Gender, Civil Status, Birthdate, Birth Place, Date Hired, Address, Telephone no.), Additional Information, Dependents, Family Background, In Case of Emergency, Past Employment Record, Educational Background, Seminars and Trainings, Assessments and Exams, Skills / Awards / Licenses, Violations, Medical/Drug Tests, Employment History. *Documents*: table (Documents Type, Documents Name, File Size, Date Modified, Original Filename, Action) + Dropzone upload + download/delete. *Payroll*: Basic Salary per Month, Allowance per Month (taxable), Monthly Tax Shield, Daily Rate, Daily Tax Shield, Hourly Rate, Overtime Rate/hr, Undertime Rate/hr, Include Salary Adjustment / Include Salary / Include Tax Shield, SSS Loan (+per-cutoff), HDMF Loan (+per-cutoff), Cash Advance (+per-cutoff), Other Loans (+per-cutoff) → `app_employee_payroll_profile_save`, `generate_payroll`, `update_salary_adjustment`, `generate_payslip`. Also creates leave (`create_leave_request_profile`), overtime (`create_overtime_request`/`update_overtime_request`) and accountability records (`create_new_accountability_record`/`update_accountability_record`). | tabs, **ApexCharts**, **Dropzone**, Choices, Flatpickr, modals, `pages-employee-profile.js`, `pages-account.init.js`, `pages-account-setting.init.js` |
| **Daily Time Records (DTR list)** | `app_attendance` `/manpower/daily-time-records` | `manpower/apps-attendance.html.twig` (627) | Company-wide DTR table: **Employee Code · Employee Name · Date · Check In · Check Out · Rendered Hours · Action**. Date-range filter, **Import CSV** (`import_dtr`) and **Export Manpower Monitoring** (xlsx). | List.js (`new List(...)` inline), Flatpickr range, modals |
| **Attendance detail / DTR per employee** | `app_manpower` `/manpower/attendance/{id}/{emp_code}` | `manpower/apps-manpower.html.twig` (**2 139**) | Per-employee attendance ledger: **Date · Time-In · Time-Out · Rendered Hours · Undertime · Overtime · Overtime Status · For Next Payroll · Attendance Status · Note · Actions**, plus a project/task sub-table (**Project · Task · Assigned Hours · Adjustments · Status**) and a "Create New Task" form (`submit_emp_dtr_task`). | List.js, **SweetAlert2**, Flatpickr/timepickr, inline editing |
| **Employee ↔ Project assignment** | `app_emp_projects` `/manpower/employee-projects`, `app_emp_project_id` `/manpower/employee-project/{id}` (+ JSON `app_emp_project_json`) | `manpower/apps-emp-project.html.twig` (636) | Project roster: **Employee Code · Employee Name · Action**; task list: **Task Description · Date · Assigned Time (hours & minutes) · Approval Status**. Actions: **Assign Employee** (`add_emp_proj`), **Create New Task** (`submit_emp_task`), unassign (`unassign_emp_proj`), archive (`archive_emp_proj`). | List.js, modals, Choices |
| **Manpower export** | `export_xls` `/manpower/export_xls` | — | Streams `Manpower_Monitoring_Report_YYYYMMDD.xlsx` | server-side |

### 4.4 Administration — org structure & reference data

| Page | R / U | T (lines) | Table columns | Modals / actions |
|---|---|---|---|---|
| **Division** | `division` `/management/division` | `administration/division.html.twig` (282) | Code · Name · Description · Division Head · Action | `addDivisionModal` (`submit_division`), `editDivisionModal{id}` (`update_division`), `deleteModal{id}` (`archive_division`) — Division Head is a Choices select of employees |
| **Department** | `department` `/management/department` | `administration/department.html.twig` (289) | Code · Name · Division · Description · Department Head · Action | `addDepartmentModal`/`editDepartmentModal{id}`/`deleteModal{id}` → `submit_department`/`update_department`/`archive_department` |
| **Position** | `position` `/management/position` | `administration/position.html.twig` (211) | ⚠️ **still the vendor demo table** — User ID · Name · Project · Category · Phone Number · Joining Date · Status · Action; modal is `addUserModal` and posts to `submit_form` (the *subdivision* route). Headed "Position List" but "Add Subdivision". | **Half-finished page — treat as a spec gap, not a spec.** |
| **Employee Settings (users)** | `adm_user_settings` `/administration/user-settings` | `administration/user_settings.html.twig` (**1 094**) | Employee Code · Name · Role · Cellphone No. · Action | `editEmployeeModal` → `update_emp_setting` (assign user role / account settings). Server-side pagination, SweetAlert2, Popper, `apps-hr-employee.init.js` |
| **Shifts** | `adm_shifts` `/administration/shifts` | `administration/empShifts.html.twig` (316) | Name · Shift · Days of Week · Lunch Break · Total Shift Hours · Action | Add/Edit/Archive Work Shifts → `submit_shifts`/`update_shifts`/`archive_shifts`; timepickr fields, day-of-week checkbox group |
| **Owner** | `view_owner` `/administration/owner` | `administration/owner.html.twig` (380) | Fullname · Block & Lot · Email · Contact No. · Action | `addOwnerModal`/`editOwnerModal{id}`/`deleteModal{id}` → `submit_owner`/`update_owner`/`delete_owner` |
| **Models & Facilities** | `view_models` `/administration/models` | `administration/models.html.twig` (268) | Name · Type · Action | `addModelModal`/`editModelModal{id}` → `submit_model`/`update_model`/`archive_model` |
| **Model Types** | `adm_model_types` `/administration/model-types` | `administration/model_types.html.twig` (270) | Name · Code · Action | add/edit/archive → `submit_model_types`/`update_model_types`/`archive_model_types` |

### 4.5 Projects (Project Management module)

| Page | R / U | T (lines) | Content | Notes |
|---|---|---|---|---|
| **Projects / Subdivision workspace** | `project` `/project/project` (`?t=pl#onGoingProjectsTable` deep-link from dashboard) | `project_management/apps-project.html.twig` (**1 472**) | Two stacked areas: **Subdivision Details** (selector → `select_subdivision_profile`, edit/delete subdivision) + **Phase / Number of Blocks / Number of Lots** breakdown, and **On-Going Projects List** (Code · Name · Subdivision · Description · Location · No. of Phases · Total No. of Lots · Action). Add/Edit/Delete Project modals. Links to the Subdivision Wizard and `app_emp_project_id`. | List.js, per-row modals |
| **Subdivisions** | `subdivision` `/project/subdivisions` | `project_management/apps-subdivision.html.twig` (350) | Code · Name · Location · No. of Phases · Total No. of Lots · Action | `addUserModal` (misnamed) / `editUserModal{id}` / `deleteModal{id}` → `submit_form`/`update_subdivision_form`/`delete_subdivision_form` |
| **Phase (+ Blocks)** | `phase` `/project/phase` | `project_management/apps-phase.html.twig` (514) | Name · Subdivision · Code · Total Blocks · Total Lots · Remaining Lots · Action; nested **Block Name** editor posting to `update_blocks` | uses `.editable-cell` inline editing (the one module whose permission handling *removes a class* instead of hiding) |
| **Category** | `category` `/project/category` — **not in the sidebar (link commented out)** | `project_management/apps-category.html.twig` (361) | Project · Code · Location · Description · Action | `addCategoryModal`/`editCategoryModal{id}`/`deleteModal{id}` |
| **Subdivision Wizard** | `subwizard` `/project/subwizard` | `project_management/subdivision-wizard.html.twig` (630) | 4-step wizard: **Subdivision Details → Category Details → Project Details → "Registration Successfully 🎉"**, submits `wizard_project` | `form-wizard.init.js`, `nav-tabs` step indicator |
| **Worker assignment modal** | *(included fragment)* | `project_management/worker-assignment-modal.html.twig` (80) | "Assign Projects & Workers" modal → `assign_workers_to_projects`, `update_selected_project_workers` | reusable include (rare good practice) |

### 4.6 Leave Administration

| Page | R / U | T (lines) | Content | Notes |
|---|---|---|---|---|
| **Leave Policy** | `app_leave_policy` `/leave-policy/` | `leave_policy/leave_policy.html.twig` (408) | Name · Year · Description · Days · **Calendar Color** · Type · Department · Gender · Marital · Increment amount · Years before increment · Action | Add/Edit Leave Policy modals → `app_leave_policy_create`/`app_leave_policy_update`; colour swatch input feeds the calendar |
| **Employee Leaves (balances)** | `app_employee_leaves` `/employee-leaves/` | `leave_policy/employee_leave.html.twig` (348) | Outer: Name · Policies · Year · Action. Inner per-policy grid: Leave Type · No. of days · Used Days · Carried Over Days · Total Usable Days · Carry Over Type | "Update Employee Leaves" / "Edit Employee Leaves" modals → `employee_leave_update`, `update_selected_leave` (bulk) |
| **Leave Request** | `app_leave_request` `/leave-request/` | `leave_request/apps-leave-request.html.twig` (358) | Employee Name · Policy Name · Request Date · Is Half Day · Total Leave Days · Status · Reason · Updated By · Action | Add/Update Leave Request modals + dedicated **"Approve Leave?" / "Reject Leave?"** confirm modals → `create_leave_request`, `approve_leave_request`. Status pills |
| **Leave Calendar** | `app_leave_calendar` `/leave-request/calendar` | `leave_request/apps-leave-calendar.html.twig` (135) | **FullCalendar** month view of approved leaves, colour-coded by leave policy; "Draggable Events" side panel + `event-modal` | ⚠️ still labelled `pagetitle: 'Apps', title: 'Calendar'` and driven by the stock `apps-calendar.init.js` demo initialiser |
| **Holiday Configuration** | `app_holiday` `/holidays/` | `holiday/apps-holiday.html.twig` (418) | Tabs: **Standard Holidays List** and **Standard Holidays Adjustment List** — Holiday · Date · Multiplier (Regular) · Multiplier (OT) · Action | Add/Edit Holiday Config modals + **Bulk add** (`bulk_add_holidays`) + yearly update/delete (`update_yearly_holidays_config`, `delete_yearly_holidays_config`) |

### 4.7 Overtime

| Page | R / U | T (lines) | Content | Notes |
|---|---|---|---|---|
| **Overtime Request** | `app_overtime_request` `/overtime/request` | `administration/overtime_request.html.twig` (318) | Employee Name · Reason · Overtime Hours Requested · Status · Updated By · Action | Add / Edit / Update Overtime Request modals + **"Approve Overtime?" / "Reject Overtime?"** (and leftover "Approve Leave?" / "Reject Leave?") confirms → `update_overtime_request_status`, `update_overtime_request_v2` |

### 4.8 Payroll

| Page | R / U | T (lines) | Content | Notes |
|---|---|---|---|---|
| **Payroll (generation & register)** | `view_employee_payroll` `/employee-payroll` | `payroll/apps-hr-payroll-employee.html.twig` (536) | Employee list (Employee Code · Name · Monthly Salary · Daily Salary · Action) + generated payroll table (Payroll Date Range · Remarks · Employee Code · Basic Salary · Overtime Salary · Total Salary · Total Deduction · Net Salary · Status). Actions: **Generate Payroll** (`generate_all_employees_payroll`), **Update Salary Adjustment** (`update_salary_adjustment`), open payslip (`generate_payslip`), link to `employee_profile` | Flatpickr cut-off range, modals |
| **Employee Payslip (generated)** | `generate_payslip` `/generate-employee-payslip` | `payroll/apps-hr-employee-payslip.html.twig` (130) | Printable payslip: header `#TW15090257`, **Year To Date Details**, **Payslip Details**, "Signature ____________________" | print-oriented static layout |
| **Payslip (template demo, still routed)** | `app_view_payslip` `/payroll/payslip` | `payroll/apps-hr-payroll-payslip.html.twig` (92) | "Salary Slip" — Month · Salary Amount · Deductions(TDS) · Professional Tax · Provident Fund · Net Payable · Status; "Authorized Sign" | ⚠️ **Indian-payroll vendor demo content (TDS / Provident Fund) — routed but not localised.** Not in the sidebar. |
| **Create Payslip** | `app_create_payslip` `/payroll/payslip/create` | `payroll/apps-hr-payroll-create-payslip.html.twig` (114) | Same "Salary Slip" demo form | ⚠️ same vendor-demo problem; not in the sidebar |
| **Employee Salary** | `app_emp_payroll` `/payroll/empPayroll` | `payroll/apps-hr-payroll-employee-salary.html.twig` | **BROKEN — template does not exist.** Controller renders a missing file → 500. Sidebar link is commented out. |
| **Employee Payroll Profile** | `app_employee_payroll_profile` `/employee/payroll/profile` | `employee_payroll_profile/employees-payroll-profile.html.twig` (555) | Employee Code · Name · Email · Cellphone No. · Division · Department · Position · Employment Type · Date Hired · Action + "Edit Employee Profile" modal | ⚠️ the controller's `index()` is **fully commented out** — only `…_save` / `…_update/{id}` / `…_delete/{id}` remain, so the page is unreachable from routing. Template is a near-duplicate of `manpower/apps-employees.html.twig`. |
| **Payroll Reports** | `app_payroll_reports` `/payroll-reports` | `payroll_reports/payroll_reports_generation.html.twig` (308) | **10 report generator cards**, each a small form (usually a Flatpickr date range + division/company select + Generate button) that streams an `.xlsx`: **Generate Payroll** (`generate_all_employees_payroll`), **Generate Timesheet** (`generate_mandatories_report`), **Generate Payroll Sheet** (`generate_payroll_sheet`), **Payroll Register Report** (`generate_payroll_register`), **Generate Payroll Summary** (`generate_payrollsummary`), **Generate Tax Shield Report** (`generate_taxshield_report`), **Generate Cash Advance Report** (`generate_cashadvance_report`), **Generate Salary Adjustment Report** (`generate_salaryadjustment_report`), **Generate Government Dues Report** (`generate_govdues`), **Generate Government Dues per Company Report** (`generate_company_govdues`) | leftover `addUserModal` / `deleteModal` from the vendor page |

### 4.9 Payroll configuration (statutory tables)

| Page | R / U | T (lines) | Table columns | Actions |
|---|---|---|---|---|
| **SSS Configuration** | `app_sss_config` `/sss/config` | `sss_config/sss_config.html.twig` (402) | Range of Compensation · Monthly Salary Credit (Regular SS / EC / WISP / Total, split ER / EE) · Action | Add SSS Configuration, **Import SSS Tables** (`app_sss_import_config`, file upload), edit, delete |
| **PhilHealth Configuration** | `app_phil_health_config` `/philhealth/config` | `phil_health_config/philhealth_config.html.twig` (286) | Base Rate · Employee Share · Employer Share · Minimum Cap · Maximum Cap · Action | create / update / delete |
| **Pag-IBIG Configuration** | `app_pagibig_config` `/pagibig/config` | `pagibig_config/pagibig_config.html.twig` (262) | Employee Share · Employer Share · Monthly Compensation Cap · Action | create / update / delete |
| **BIR Configuration** | `app_bir_config` `/bir/config` | `bir_config/bir_config.html.twig` (297) | Tax Bracket Name · Tax Bracket Income Range · Tax Bracket Deduction (Percentage) · Tax Bracket Deduction (Amount) · Action | Add, **Import BIR Tables** (`app_tax_import_config`), update, delete |
| **13th-month pay** | — | — | ❌ **No dedicated 13th-month UI exists in the frontend.** It is handled inside payroll generation / reports only. |

> All four config pages have `{% block title %}Model Type{% endblock %}` and an
> "Edit Model Type" modal heading — **copy-paste artefacts** from
> `administration/model_types.html.twig`.

### 4.10 Users, roles & permissions / Super Admin

| Page | R / U | T (lines) | Content |
|---|---|---|---|
| **Roles and Access** | `super_roles` `/super/user-roles` | `super_admin/roles_permission.html.twig` (448) | "User Roles List" (Name · Code · Action) + a **permission matrix**: rows = modules, columns = **View / Add / Edit / Delete** checkboxes. Module display names come from a Twig map: `{'administration':'Administration','humanres':'Human Resources','project':'Project Management','payroll':'Payroll Administration','emp_leaves':'Leave Administration'}`. Add User Role modal (`submit_user_roles`), Edit Permission (`update_role_access`), delete (`delete_user_roles`). Visible to `SADM`/`ADM` only. |
| **ALPMC Sync** | `super_sync` `/super/admin` | `super_admin/workers_sync.html.twig` (232) | "Connection List" — Username · Database Name · Host · Action; Add Connection modal. ⚠️ `{% block title %}Division{% endblock %}`, modal id `addDivisionModal`, and it posts to **`submit_division`** — copy-pasted from the Division page. `SADM` only. |

### 4.11 Notifications / profile / settings

- **Notifications** — no page; only the topbar dropdown (§2.5), rendered from
  `session.notification_message`.
- **Profile** — no separate "my profile" page; the topbar menu links to the
  shared **Employee Profile** at `employee_profile/{session.empCode}`.
- **Settings** — no application settings page. The only "settings" UI is the
  **Theme Customizer** drawer (`partials/_customizer.html.twig`, 22 KB) which is
  pure vendor chrome (layout/skin/mode/direction/width/sidebar-size/navbar/
  sidebar & topbar colours + Reset).
- **Accountability** — no standalone route/page; it is the
  **"Accountability Records" tab inside Employee Profile**
  (`create_new_accountability_record`, `update_accountability_record`).
- **Manpower** — likewise not a standalone page in the live menu; "manpower" is
  the attendance/DTR + employee-project surface (§4.3) plus the
  `export_xls` Manpower Monitoring report.

### 4.12 Orphan / broken live-namespace templates

| File | Lines | Status |
|---|---|---|
| `employee_leaves/index.html.twig` | 20 | **Symfony maker stub** — `<h1>Hello EmployeeLeavesController! ✅</h1>` with a hard-coded `E:/xampp/htdocs/...` path. Never rendered. |
| `employee_payroll/index.html.twig` | 20 | same stub |
| `overtime_request/index.html.twig` | 20 | same stub |
| `error/index.html.twig` | 20 | same stub (`ErrorController` only redirects to `referer`) |
| `employee201/forms-validation.html.twig` | 104 | `employee201_form` `/employee201/forms` — still the vendor **"Browser Default / Sign Up Form"** validation demo |
| `payroll/apps-hr-payroll-employee-salary.html.twig` | — | **missing file, controller renders it** → fatal |
| `phil_health_config/create.html.twig` | — | **missing file, controller renders it** → fatal |
| `employee_payroll_profile/save.html.twig` | — | **missing file, controller renders it** → fatal |
| `manpower/apps-subdivision.html.twig` | — | **missing file**, referenced in a commented-out action |
| `apps-hr-employee.html.twig` (root) | 194 | referenced by a commented-out `HomeController::root()` catch-all; vendor demo |

---

## 5. Styling Approach & Build Pipeline

### 5.1 What actually builds what — two disconnected pipelines

**Pipeline A — Webpack Encore (`webpack.config.js` + `package.json`) — effectively EMPTY.**

```js
Encore
  .setOutputPath('public/build/')
  .setPublicPath('/build')
  .addEntry('app', './assets/app.js')
  .splitEntryChunks().enableSingleRuntimeChunk()
  .cleanupOutputBeforeBuild().enableBuildNotifications()
  .enableSourceMaps(!Encore.isProduction())
  .enableVersioning(Encore.isProduction())
  .configureBabelPresetEnv(config => { config.useBuiltIns='usage'; config.corejs='3.23'; })
  // .enableSassLoader()      <-- COMMENTED OUT
  // .enableReactPreset()     <-- COMMENTED OUT
;
```
and the single entry is:
```js
// assets/app.js
import './styles/app.css';   // assets/styles/app.css is 45 bytes
```
- `assets/` contains only `app.js` (302 B) and `styles/app.css` (45 B).
- **`public/build/` does not exist** and `base.html.twig` never calls
  `encore_entry_link_tags()` / `encore_entry_script_tags()`.
- `package.json` deps are misleading: it declares `bootstrap@5.3.2`,
  `node-sass@^9`, `rtlcss`, `rtlcss-webpack-plugin`, `postcss-rtl`,
  `@hotwired/stimulus`, `@symfony/stimulus-bridge` — **none of which are used**
  (no Stimulus controllers exist, no Bootstrap JS is loaded, RTL CSS is never
  generated). There is **no Tailwind, PostCSS, autoprefixer or Sass entry in
  `package.json` at all**.

**Pipeline B — the real one: pre-compiled Tailwick assets committed to `public/assets/`.**

`public/assets/scss/` holds the *sources* the vendor used, but they are compiled
**out-of-band** (their `@import`s point at `../../../node_modules/...`, and
`node_modules/` is not in the repo):

```scss
/* public/assets/scss/tailwind.scss (29 lines) */
@import "fonts/fonts";                                                  // Public Sans from Google
@import "../../../node_modules/choices.js/public/assets/styles/choices.min.css";
@import "../../../node_modules/flatpickr/dist/flatpickr.min.css";
@import "../../../node_modules/leaflet/dist/leaflet.css";
@import "../../../node_modules/swiper/swiper-bundle.css";
@import "../../../node_modules/vanilla-calendar-pro/build/vanilla-calendar.min.css";
@import "../../../node_modules/gridjs/dist/theme/mermaid.min.css";
@tailwind base; @tailwind components; @tailwind utilities;
@import "plugins/gridjs";
.group\/menu-link:hover, .animate { animation-iteration-count: 2; stroke-dasharray: 10; }
```
```scss
/* public/assets/scss/icons.scss (9 lines) */  @import 'remixicon/fonts/remixicon.css';
/* public/assets/scss/fonts/fonts.scss (4 lines) */ @import url('…Public+Sans…');
/* public/assets/scss/plugins/_gridjs.scss (101 lines) */ // Grid.js dark/light theme via @apply — UNUSED
```

Everything the browser loads is a **committed, minified artefact**:

| Asset | Size | Loaded from |
|---|---|---|
| `public/assets/css/tailwind2.css` | 660 KB | `_head-css.html.twig` — the live stylesheet |
| `public/assets/css/tailwind.css` | 552 KB | orphaned older build |
| `public/assets/css/icons.css` (+ 4 remixicon font files, ~1.3 MB) | 108 KB | `_head-css.html.twig` |
| `public/assets/css/page-loader.css` | 630 B | `_head-css.html.twig` |
| `public/assets/js/tailwick.bundle.js` | 30 KB | `_vendor-scripts.html.twig` |
| `public/assets/js/app.js` | 54 KB | per page (81 `<script>` occurrences across templates) |
| `public/assets/js/common.js` | 9 KB | 6 pages (modals/drawers/tabs/collapse/dropdowns) |
| `public/assets/js/layout.js` | 2 KB | `_head-css` (first script, pre-paint) |
| `public/assets/js/api.js`, `permission.js`, `global_functions.js` | 3–5 KB each | `_vendor-scripts.html.twig` |

`assets/scss/plugins/_gridjs.scss` is the only *custom* SCSS in the project, and
its target library (Grid.js) is never used. In practice:
**custom SCSS ≈ 0. The styling is 100 % Tailwind utility classes written inline in Twig.**

> ⚠️ **Critical for maintenance:** because `tailwind2.css` is a committed,
> content-purged build with no config in-repo, **any new Tailwind class written
> in a template silently does nothing** unless it already happens to exist in
> the compiled file. This is a large hidden constraint on the current codebase
> and a strong argument for a proper rebuild.

### 5.2 Load order actually emitted per page

`_head-css.html.twig` (in `<head>`):
1. `assets/js/layout.js` — *a script in the head*, restores `data-*` from `sessionStorage`
2. `assets/css/icons.css` (Remix Icon)
3. `assets/libs/flatpickr/flatpickr.min.css`
4. `assets/libs/choices.js/public/assets/styles/choices.min.css`
5. `assets/css/tailwind2.css`
6. `assets/css/page-loader.css`

`_vendor-scripts.html.twig` (bottom of `<body>`):
`choices.min.js` → `popper.min.js` → `tippy-bundle.umd.min.js` → `simplebar.min.js`
→ `prism.js` → `lucide.js` → `tailwick.bundle.js` → `flatpickr.min.js`
→ `jquery-3.7.1.min.js` → `toastify.js` → **`flatpickr.min.js` (again)** →
`api.js` → `permission.js` → `global_functions.js`

then `{% block javascripts %}` per page (usually `list.js`, `list.pagination.js`,
`app.js`, and an inline `<script>`).

Consequences: **~2.5 MB of CSS+JS on every page load**, jQuery loading *after*
several plugins, Prism/Tippy/SimpleBar shipped to pages that never use them, and
Flatpickr parsed twice.

### 5.3 How a React (Vite + Tailwind) rewrite reproduces the look

**1. Recreate the theme config** (there is none to copy — write it from §1):
```ts
// tailwind.config.ts
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: { public: ['"Public Sans"', 'sans-serif'] },
      colors: {
        custom: { 50:'#eff6ff',100:'#dbeafe',200:'#bfdbfe',300:'#93c5fd',400:'#60a5fa',
                  500:'#3b82f6',600:'#2563eb',700:'#1d4ed8',800:'#1e40af',900:'#1e3a8a' },
        zink:   { 50:'#f4f7fb',100:'#c8d7e9',200:'#92afd3',300:'#5885bc',400:'#395f8e',
                  500:'#233a57',600:'#1c2e45',700:'#132337',800:'#0f1824',900:'#070c12' },
        'body-bg': '#f1f5f9',
        topbar:    '#ffffff',
        'topbar-border':        '#e2e8f0',
        'topbar-item':          '#334155',
        'vertical-menu':        '#ffffff',
        'vertical-menu-border': '#e2e8f0',
        'vertical-menu-sub-item': '#94a3b8',
        brand: { navy: '#002a45' },        // the topbar title colour
      },
      spacing: { header: '4.375rem', 'vertical-menu': '16.25rem',
                 'vertical-menu-md': '10rem', 'vertical-menu-sm': '4.5rem' },
      fontSize: { 15:'15px', 16:'16px', 17:'17px', 19:'19px', 20:'20px' },
      borderRadius: { DEFAULT: '0.375rem' },
    },
  },
};
```
Load Public Sans (self-host via `@fontsource/public-sans` rather than the Google
`@import`), and replace Remix Icon + Lucide with **`lucide-react` only** —
the only Remix glyphs actually needed are the sidebar chevron and the breadcrumb
separator, both trivially replaced by `<ChevronDown/>` / `<ChevronRight/>`.

**2. Replace the `group-data-[…]` state machine with React state.**
Drop `data-layout`, `data-skin`, `data-navbar`, `data-content`, `dir`,
`data-sidebar`, `data-topbar` entirely — the app only ever uses
*vertical + fluid + LTR + default skin*. Keep **two** pieces of state:
`sidebarCollapsed: boolean` and `theme: 'light' | 'dark'` (persist in
`localStorage`, not `sessionStorage`), driving `<html class="dark">` and a
`w-[16.25rem]` / `w-[4.5rem]` sidebar.

**3. Build ~14 primitives** that cover every real page:
`AppShell` (Sidebar + Topbar + Footer), `NavItem`/`NavGroup`,
`PageHeader` (the breadcrumb component), `Card`/`CardBody`,
`DataTable` (TanStack Table = search + sort + paginate + empty state, replacing
List.js and the two other table strategies), `Modal`, `ConfirmDialog`,
`Drawer`, `Button`, `Input`/`Select`/`Checkbox`/`Switch` (`react-hook-form` + `zod`),
`DatePicker`/`TimePicker`/`DateRangePicker`, `Dropdown` (Radix),
`Badge`/`StatusPill`, `Tabs`, `Toast` (sonner), `Can` (permission guard).

**4. Kill the anti-patterns** listed throughout this doc:
per-row modals → one modal + selected-row state; render-then-hide permissions →
server-filtered data + `<Can>`; whole-dataset server rendering → paginated API;
`{{ errorScript|raw }}` / `{{ javascriptSnippet|raw }}` → typed state.

**5. Styling parity checklist** (highest-signal classes to port verbatim):
`bg-body-bg` page · `.card` = `rounded-md border border-slate-200 bg-white p-0 mb-5 dark:bg-zink-700 dark:border-zink-600`
· `.card-body` = `p-5` · headings `text-15`/`text-16` · inputs
`rounded-md border-slate-200 focus:border-custom-500 focus:outline-none` ·
primary button `bg-custom-500 hover:bg-custom-600 focus:ring focus:ring-custom-100 text-white rounded-md px-4 py-2` ·
table `border-separate border-spacing-y-1` with `thead tr` on `bg-slate-100 dark:bg-zink-600`
and `[&.active]:after:border-custom-500` left accent.

**6. Data layer.** Today's frontend already talks to a **separate REST API**
(`public/assets/js/api.js` hard-codes `http://127.0.0.1:8000/` for the API and
`http://127.0.0.1:8001/validate_call` for the token, with commented-out prod URLs
`https://hris-services.wrldcapitalholdings.com/` and
`http://wchhrisservices.techrostrum.com/`). That means a React SPA can consume
the same API directly — the Twig layer is mostly a pass-through. Replace
`api.js`'s cached-token `$.ajax` singleton with an axios/fetch client +
TanStack Query.

---

## 6. Unused Template Boilerplate — DO NOT PORT

### 6.1 The numbers

| Metric | Count |
|---|---|
| `.html.twig` files in `templates/` (all) | **213** |
| Templates at `templates/` root | **151** |
| Root templates that are LIVE | **2** (`dashboards-hr.html.twig`, `auth-login-boxed.html.twig`) |
| Root templates that are DEAD vendor demos | **149** |
| Dead root templates — total lines | **34 870** |
| Dead root templates — total size | **3.74 MB** |
| Total lines across all templates | **58 273** |
| Live application templates (rendered + partials + component + email + fragment) | **~59** (41 rendered-and-present, 3 rendered-but-missing, 15 partials) |

**≈ 60 % of all Twig lines and ≈ 70 % of all files are dead vendor demos.**

### 6.2 Dead root templates, grouped (all 149 — delete on sight)

**Ecommerce (9)** — `apps-ecommerce-cart`, `-checkout`, `-order-overview`,
`-orders`, `-product-create`, `-product-grid`, `-product-list`,
`-product-overview`, `-sellers`.
*(Note: `_topbar.html.twig`'s cart drawer still links to two of these.)*

**Vendor HR demos (13) — the dangerous ones, they look real:**
`apps-hr-employee`, `apps-hr-department`, `apps-hr-holidays`,
`apps-hr-attendance`, `apps-hr-attendance-main`, `apps-hr-leave`,
`apps-hr-leave-employee`, `apps-hr-create-leave`, `apps-hr-create-leave-employee`,
`apps-hr-sales-estimates`, `apps-hr-sales-payments`, `apps-hr-sales-expenses`,
plus **`apps-manpower.html.twig` at the root** (an unused twin of the live
`manpower/apps-manpower.html.twig`).
⚠️ These are the Tailwick *sample* HR pages that the real pages under
`templates/manpower/`, `templates/holiday/`, `templates/leave_*/` were copied
from. Do not mistake them for the application.

**ApexCharts demos (18)** — `charts-apex-area`, `-bar`, `-boxplot`, `-bubble`,
`-candlstick`, `-column`, `-funnel`, `-heatmap`, `-line`, `-mixed`, `-pie`,
`-polar`, `-radar`, `-radialbar`, `-range-area`, `-scatter`, `-timeline`, `-treemap`.

**UI element demos (18)** — `ui-alerts`, `-avatar`, `-buttons`, `-cards`,
`-collapse`, `-countdown`, `-drawer`, `-dropdown`, `-gallery`, `-label`,
`-lists`, `-modal`, `-notification`, `-progress-bar`, `-spinners`, `-timeline`,
`-tooltip`, `-video`.

**Form demos (16)** — `forms-basic`, `-checkbox-radio`, `-clipboard`,
`-colorpicker`, `-datepicker`, `-editor-balloon`, `-editor-classic`,
`-editor-inline`, `-file-upload`, `-input-mask`, `-input-spin`, `-multi-select`,
`-select`, `-switches`, `-timepicker`, `-wizard`.

**Auth variants (26)** — every `auth-*-basic/-boxed/-cover/-modern` combination
for login, register, logout, verify-email, two-steps, reset-password,
create-password **except** the two actually used
(`auth-login-boxed.html.twig` and the two files under `forget_password/`).

**Dashboards (4)** — `index.html.twig` (873 lines — the Tailwick default
*Ecommerce* dashboard; **not** the app home), `dashboards-analytics`,
`dashboards-email`, `dashboards-social-media`.

**Apps (15)** — `apps-chat` (**167 KB!**), `apps-mailbox`, `apps-notes`,
`apps-calendar`, `apps-calendar-month-grid`, `apps-calendar-multi-month-stack`,
`apps-invoice-list`, `apps-invoice-add-new`, `apps-invoice-overview`,
`apps-social-event`, `apps-social-friends`, `apps-social-marketplace`,
`apps-social-video`, `apps-users-list`, `apps-users-grid`.

**Tables (4)** — `tables-basic`, `tables-datatable`, `tables-gridjs`,
`tables-listjs`. *(Only `tables-listjs` reflects the pattern actually used.)*

**Navigation demos (4)** — `navigation-navbars`, `-tabs`, `-breadcrumb`, `-pagination`.

**Plugin demos (6)** — `plugins-lightbox`, `-scroll-hint`, `-simplebar`,
`-sweetalert`, `-swiper-slider`, `-video-player`.

**Maps (2)** — `maps-google`, `maps-leaflet`.
**Icons (2)** — `icons-lucide`, `icons-remix`.
**Landing (2)** — `onepage-landing`, `product-landing`.
**Pages (10)** — `pages-account`, `pages-account-settings`, `pages-pricing`,
`pages-faqs`, `pages-contact-us`, `pages-coming-soon`, `pages-maintenance`,
`pages-offline`, `pages-404`, `pages-starter`.

*(9 + 13 + 18 + 18 + 16 + 26 + 4 + 15 + 4 + 4 + 6 + 2 + 2 + 2 + 10 = **149**.)*

### 6.3 Dead code *inside* live files (easy to miss)

| Location | Dead content |
|---|---|
| `partials/_sidebar.html.twig` | **~90 % of the file** — the entire Tailwick demo menu (Ecommerce, HR Management, Email, Calendar, Notes, Social, Invoices, Users, Authentication, Pages, UI Elements, Plugins, Navigation, Forms, Tables, Apexcharts, Icons, Maps, Multi Level "Level 1.1/2.1/3.1") is inside `{# … #}`. Also a commented-out *second* "Dashboards" group containing Manpower Monitoring / Payroll / Administration / Super Administration submenus. |
| `partials/_topbar.html.twig` | The full **`#cartSidePenal` e-commerce cart drawer** (~125 lines, 3 demo products, `TECHROSTRUM50` coupon, `$2,531.17`, links to `apps-ecommerce-*`) — *still rendered into the DOM on every page*. Plus the commented-out 9-language flag dropdown and Inbox/Chat/Upgrade-Pro menu items. |
| `partials/_customizer.html.twig` | 22 KB / 197 lines of theme-switcher UI for layout modes the app never uses (Horizontal, Semi-Dark, Bordered skin, RTL, Boxed, 4 sidebar colours, 4 navbar types). |
| `partials/_page-title.html.twig`, `partials/_title-meta.html.twig` | Broken PHP-in-Twig (`<?= $title ?>`); not included anywhere. |
| `dashboards-hr.html.twig` | The "Overall Employees" table and "Upcoming Scheduled" vanilla-calendar widget are commented out, but their `<script>` tags still load. |
| `templates/{employee_leaves,employee_payroll,overtime_request,error}/index.html.twig` | Four Symfony **maker stubs** ("Hello XController! ✅") with hard-coded `E:/xampp/htdocs/Techrustrom/...` paths. |
| `templates/employee201/forms-validation.html.twig` | Routed (`/employee201/forms`) but is the vendor "Sign Up Form" validation demo. |
| `src/Controller/*` | Several actions are 90 % commented-out code (`EmployeePayrollProfileController::index`, `ManpowerController::viewSubdivision`, `HomeController::root`, `LeavePolicyController::createLeavePolicy` v1, `EmployeeProfileController::uploadAtachment` v1). |

### 6.4 Dead *assets* (safe to drop from the rewrite)

- **Libraries never referenced by a live page (29 of 38):** `@ckeditor`,
  `@simonwep`, `aos`, `cleave.js`, `clipboard`, `cropperjs`, `draggable`,
  `echarts`, `funnel-graph-js`, `glightbox`, `gmaps`, `gridjs`, `gsap`,
  `leaflet`, `leaflet-routing-machine`, `list.js` demos, `moment`, `multi.js`,
  `nouislider`, `plyr`, `read-smore`, `scroll-hint`, `swiper`, `prismjs`
  *(loaded globally but unused)*, plus `public/assets/select2/` and
  `public/assets/js/datatables/*` (DataTables + Buttons + JSZip + pdfmake +
  vfs_fonts + a **second jQuery 3.7.0**).
- **`public/assets/js/pages/*` — 76 init scripts, only 12 referenced** by live
  pages (`apps-list-init`, `apps-user-list.init`, `apps-hr-employee.init`,
  `pages-employees`, `pages-employee-profile`, `pages-account.init`,
  `pages-account-setting.init`, `form-wizard.init`, `form-validation.init`,
  `auth-login.init`, `apps-calendar.init`, `dashboards-hr.init` *(commented out)*).
- `public/assets/css/tailwind.css` (552 KB) — superseded by `tailwind2.css`.
- `public/assets/scss/plugins/_gridjs.scss` — themes a library nobody loads.
- `public/build/` never generated; `assets/app.js` + `assets/styles/app.css` are
  45–302 byte stubs.
- Stray artefacts committed to `public/`:
  `Manpower_Monitoring_Report_2024100{4,6}.xlsx`, `…20241016.xlsx`, `…20241017.xlsx`.

### 6.5 Rewrite effort guidance

Port, in this order:
1. **AppShell + auth** (login, forgot/reset password) — 4 screens.
2. **The 14 primitives** in §5.3 step 3.
3. **CRUD reference pages** (Division, Department, Owner, Models, Model Types,
   Shifts, Subdivision, Phase, Category, Leave Policy, SSS/PhilHealth/Pag-IBIG/BIR)
   — 13 near-identical `DataTable + Modal` screens; one generic
   `<ResourcePage>` covers them all.
4. **Employee Masterlist + Employee Profile** — the profile (4 513 lines, 8 tabs)
   is by far the largest single work item; budget it as 8 sub-features.
5. **Attendance / DTR** (list + per-employee ledger, 2 766 lines combined).
6. **Leave** (requests, balances, calendar, holidays) and **Overtime**.
7. **Payroll** (generation, payslip, reports) — note the payslip templates are
   still un-localised vendor demos and must be **designed, not ported**.
8. **Roles & permissions matrix**, **ALPMC Sync**, **Dashboard**.

Do **not** port: any file in §6.2, the Theme Customizer, the cart drawer, the
horizontal/RTL/boxed layout modes, `position.html.twig`'s demo table, and the
Indian-payroll payslip demos.

---

## 7. Quick-Reference Cheat Sheet

| Question | Answer |
|---|---|
| Template product | **Tailwick – Admin & Dashboard Template v1.1.0**, Themesdesign |
| Brand accent | `custom-500` = **`#3b82f6`**, hover `custom-600` = `#2563eb` |
| Corporate navy | `#002a45` (topbar title only) |
| Page bg / card bg | `#f1f5f9` / `#ffffff` (dark: `#0f1824` / `#132337`) |
| Font | **Public Sans** 200–700, Google Fonts |
| Icons | Lucide (primary) + Remix Icon (font glyphs) |
| Sidebar width / topbar height | `16.25rem` (260 px) / `4.375rem` (70 px) |
| Layout state | `data-*` attributes on `<html>` + `sessionStorage` |
| Menu source | **hand-written HTML in an 866 KB Twig partial** |
| Active route | `querySelector('[href="'+location.pathname+'"]')` — exact match only |
| Tables | **List.js + List.Pagination.js** (28 pages); 3 pages server-paginated; no Grid.js / no DataTables |
| Modals & drawers | Tailwick `data-modal-target` / `data-drawer-target` (`common.js`) — **no Bootstrap JS** |
| Selects | **Choices.js** via `data-choices` |
| Dates/times | **Flatpickr** via `data-provider="flatpickr" \| "timepickr"` |
| Toasts | **Toastify JS**, `bg-green-500` / `bg-red-500`, top-right, 3 s |
| Confirms | bespoke delete modal (mostly) + SweetAlert2 (4 pages) |
| Charts | ApexCharts (Employee Profile only) |
| Calendar | FullCalendar (Leave Calendar only) |
| Uploads | Dropzone (Employee Profile) + plain `<input type="file">` elsewhere |
| Validation | **native HTML5 + ad-hoc jQuery** — no validation library, no CSRF |
| Permissions | class-name-based DOM hiding (`permission.js`) from `<body data-user-permissions>` |
| Breadcrumb | `#[AsTwigComponent('breadcrumb')]` — the one real component (154 usages) |
| Build | **no working build** — pre-compiled `tailwind2.css` (660 KB) committed; Encore config is an empty stub |
| Dead weight | **149 / 151** root templates unused = 34 870 lines / 3.74 MB |
