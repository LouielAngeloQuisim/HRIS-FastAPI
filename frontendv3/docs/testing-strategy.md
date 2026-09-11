# Frontend Automated Testing Strategy
## HRIS Python — `frontendv3`

## 1. Current State Assessment

| Layer | Framework | Status | Gap |
|---|---|---|---|
| Component / integration | Vitest + `vitest-browser-react` | **Active** — 78 files, 263 tests | Missing submit-flow assertions, error-state coverage for new forms |
| E2E | Playwright (`e2e/*.spec.ts`) | **Active** — 25 spec files, 24 page objects, full CRUD coverage | Covers login, navigation, create/edit/delete, permission matrix, approval flows, empty/error states |
| Lint / type | ESLint + TypeScript | Active | 14 pre-existing errors, 5 warnings (not introduced by recent changes) |
| Coverage | Vitest `coverage-v8` | Configured; UI components excluded | Needs enforcement gate in CI |

## 2. Testing Pyramid

```
        /\    E2E — Playwright (critical user journeys)
       /  \
      /    \  Integration — Vitest browser (feature + form flows)
     /      \
    /        \ Unit — Vitest browser (components, hooks, utils)
   /__________\
```

**Rationale:**
- **E2E (Playwright):** Validates full user journeys across the real app: login → navigate → CRUD → logout. Run in CI on every PR.
- **Integration (Vitest browser):** Validates feature-level behavior with mocked API but real DOM. Fast feedback during development.
- **Unit (Vitest browser):** Validates individual components, hooks, and form logic in isolation.

## 3. Vitest Component / Integration Testing Strategy

### 3.1 Test File Convention

Colocate tests beside source files. One test file per concern:

```
src/features/<feature>/
  index.test.tsx                ← page-level: renders, permissions, empty/loading/error
  heading.test.tsx              ← page title, record count, toolbar
  row-actions.test.tsx          ← approve/reject buttons, permission gating
  data-fidelity.test.tsx        ← backend data rendered unmodified
  retry.test.tsx                ← error-state retry button
  permissions.test.tsx          ← useCan() gating for view/edit/delete
  components/
    <feature>-form.test.tsx     ← create/edit form submission, validation, cancel
```

### 3.2 Test Utilities

**`src/test-utils/providers.tsx`** — already exists:
- `renderWithClient(ui)` wraps UI in `QueryClientProvider` with `retry: false`.

**Recommended addition: `src/test-utils/mocks.ts`** for shared mock factories:
```ts
export function mockUseCan(permissions: Record<string, boolean>) {
  return vi.fn((module: string, action: string) =>
    permissions[`${module}:${action}`] ?? false
  )
}

export function mockQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
}
```

### 3.3 Standard Test Patterns

#### Pattern A: Page renders and shows correct states
```ts
it('renders the page title', async () => {
  useQueryMock.mockReturnValue({ data: null, isPending: true, isError: false, refetch: vi.fn() })
  const screen = await render(<FeaturePage />)
  await expect.element(screen.getByText('Feature Name')).toBeVisible()
})

it('shows loading state', async () => {
  useQueryMock.mockReturnValue({ data: null, isPending: true, isError: false, refetch: vi.fn() })
  const screen = await render(<FeaturePage />)
  await expect.element(screen.getByText('Loading...')).toBeVisible()
})

it('shows error state with retry', async () => {
  useQueryMock.mockReturnValue({ data: undefined, isPending: false, isError: true, refetch: vi.fn() })
  const screen = await render(<FeaturePage />)
  await expect.element(screen.getByText('Failed to load...')).toBeVisible()
  await userEvent.click(screen.getByRole('button', { name: /try again/i }))
  expect(refetchMock).toHaveBeenCalled()
})

it('renders empty state when no data', async () => {
  useQueryMock.mockReturnValue({ data: { data: [], count: 0 }, isPending: false, isError: false, refetch: vi.fn() })
  const screen = await render(<FeaturePage />)
  await expect.element(screen.getByText('No records found.')).toBeVisible()
})
```

#### Pattern B: Permission gating
```ts
it('hides edit/delete buttons for low-privilege user', async () => {
  vi.mocked(useCan).mockImplementation((_module: string, _action: string) => false)
  useQueryMock.mockReturnValue({ data: mockListWithOnePending, isPending: false, isError: false, refetch: vi.fn() })
  const screen = await render(<FeaturePage />)
  await expect.element(screen.queryByRole('button', { name: /approve/i })).not.toBeInTheDocument()
})
```

#### Pattern C: Approve / Reject actions
```ts
it('approves a pending item and invalidates queries', async () => {
  const invalidateSpy = vi.fn()
  useQueryClient.mockReturnValue({ invalidateQueries: invalidateSpy })
  useApproveMock.mockReturnValue({ mutateAsync: vi.fn().mockResolvedValue(undefined), isPending: false })

  useQueryMock.mockReturnValue({ data: mockPending, isPending: false, isError: false, refetch: vi.fn() })
  const screen = await render(<FeaturePage />)
  await userEvent.click(screen.getByRole('button', { name: 'Approve' }))

  await vi.waitFor(() => expect(approveMutateAsync).toHaveBeenCalledWith(mockPending.data[0].id))
  await vi.waitFor(() => expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['feature'] }))
})
```

#### Pattern D: Form submission
```ts
it('submits the form and closes on success', async () => {
  const onClose = vi.fn()
  const mutateAsync = vi.fn().mockResolvedValue({ id: 'new-1' })
  useCreateMock.mockReturnValue({ mutateAsync, isPending: false })

  const screen = await render(<FeatureForm open={true} onClose={onClose} />)
  await userEvent.fill(screen.getByLabelText(/Name/i), 'New Item')
  await userEvent.click(screen.getByRole('button', { name: /submit/i }))

  await vi.waitFor(() => expect(mutateAsync).toHaveBeenCalledWith({ name: 'New Item' }))
  await vi.waitFor(() => expect(onClose).toHaveBeenCalled())
})
```

#### Pattern E: Mutation pending state disables buttons
```ts
it('disables approve button while mutation is pending', async () => {
  useApproveMock.mockReturnValue({ mutateAsync: vi.fn(), isPending: true })
  useQueryMock.mockReturnValue({ data: mockPending, isPending: false, isError: false, refetch: vi.fn() })
  const screen = await render(<FeaturePage />)
  const approveBtn = screen.getByRole('button', { name: 'Approve' })
  await expect.element(approveBtn).toBeDisabled()
})
```

### 3.4 Mocking Conventions

- **Always hoist mocks** with `vi.hoisted()` before `vi.mock()`.
- **Mock at the API-hook level** (`@/lib/api/<feature>`), not at the service layer — tests should exercise the feature component, not the backend client.
- **Mock `useCan`** explicitly per test when testing permission gating; default to `() => true` only for smoke tests.
- **Never mock child components** unless the child itself is the test target. If a child is complex, extract it and test it separately.

## 4. Playwright E2E Testing Strategy

### 4.1 Directory Layout

```
frontendv3/
  e2e/
    auth/
      login.spec.ts
      logout.spec.ts
      token-refresh.spec.ts
      permissions.spec.ts
    attendance/
      daily-time-records.spec.ts
      dtr-adjustments.spec.ts
      leave-requests.spec.ts
      leave-calendar.spec.ts
      leave-ledger.spec.ts
      holidays.spec.ts
    organization/
      divisions.spec.ts
      departments.spec.ts
      subdivisions.spec.ts
      positions.spec.ts
    projects/
      projects.spec.ts
      phases.spec.ts
      blocks.spec.ts
      lots.spec.ts
      categories.spec.ts
      models.spec.ts
      model-types.spec.ts
      owners.spec.ts
    rbac/
      roles.spec.ts
    employees/
      employees.spec.ts
      employee-projects.spec.ts
      emp-tasks.spec.ts
    dashboard/
      dashboard.spec.ts
    fixtures/
      auth.fixture.ts       ← login helper, seeded test data
      api.fixture.ts        ← direct API helpers for test setup/teardown
    helpers/
      selectors.ts          ← data-testid maps, text selectors
      assertions.ts         ← custom matchers
    global-setup.ts
    global-teardown.ts
```

### 4.2 Naming Convention

- `*.spec.ts` — Playwright test files
- Group by domain under `e2e/<domain>/`
- Test titles: `should <action> when <condition>`

### 4.3 Base Fixtures

**`e2e/fixtures/auth.fixture.ts`**
```ts
import { type Page, type APIRequestContext } from '@playwright/test'

export interface AuthFixtures {
  loginAsAdmin: () => Promise<void>
  loginAsUser: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  apiRequest: APIRequestContext
}

export async function injectAuthFixtures(page: Page): Promise<AuthFixtures> {
  const apiRequest = page.request
  const BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:5173'
  const API_URL = process.env.E2E_API_URL || 'http://localhost:8000/api/v1'

  async function login(email: string, password: string) {
    await page.goto(`${BASE_URL}/login`)
    await page.locator('input[type="email"]').first().fill(email)
    await page.locator('input[type="password"]').first().fill(password)
    await page.locator('button[type="submit"]').first().click()
    await expect(page).toHaveURL(/.*dashboard/, { timeout: 10000 })
  }

  return {
    loginAsAdmin: () => login('admin@example.com', 'changethis'),
    loginAsUser: (email, password) => login(email, password),
    logout: async () => {
      await page.request.post(`${API_URL}/logout`)
      await page.goto(`${BASE_URL}/login`)
      await expect(page).toHaveURL(/.*login/, { timeout: 5000 })
    },
    apiRequest,
  }
}
```

**`e2e/fixtures/api.fixture.ts`**
```ts
import { type APIRequestContext } from '@playwright/test'

export async function seedTestData(request: APIRequestContext) {
  // Create test divisions, departments, etc. via direct API calls
  // Returns IDs for cleanup
}

export async function cleanupTestData(request: APIRequestContext, ids: string[]) {
  // Delete seeded data
}
```

### 4.4 Global Setup / Teardown

Add to `playwright.config.ts`:
```ts
globalSetup: require.resolve('./e2e/global-setup.ts'),
globalTeardown: require.resolve('./e2e/global-teardown.ts'),
```

- **`e2e/global-setup.ts`** — seed test database before all tests run.
- **`e2e/global-teardown.ts`** — clean up seeded data.

### 4.5 Selector Strategy

**Prefer `data-testid` attributes** for stable selectors. Add them to key interactive elements:

```tsx
// src/features/divisions/index.tsx
<Button data-testid="add-division-button" onClick={...}>Add Division</Button>
<Button data-testid="edit-division-button" onClick={...}>Edit</Button>
<button data-testid="delete-division-button" onClick={...}>Delete</button>
```

**`e2e/helpers/selectors.ts`**
```ts
export const Selectors = {
  addButton: (resource: string) => `[data-testid="add-${resource}-button"]`,
  editButton: (resource: string, index = 0) => `[data-testid="edit-${resource}-button"]:nth(${index + 1})`,
  deleteButton: (resource: string, index = 0) => `[data-testid="delete-${resource}-button"]:nth(${index + 1})`,
  confirmDialog: {
    confirm: () => '[data-testid="confirm-delete-button"]',
    cancel: () => '[data-testid="cancel-delete-button"]',
  },
  table: () => '[role="table"], table',
  row: (index: number) => `[role="row"]:nth(${index + 1}), table tbody tr:nth(${index + 1})`,
}
```

### 4.6 Page Object Model (POM)

Create page objects for each feature to encapsulate selectors and actions:

```ts
// e2e/pages/divisions.page.ts
import { type Page, type Locator } from '@playwright/test'

export class DivisionsPage {
  readonly page: Page
  readonly addButton: Locator
  readonly table: Locator
  readonly rows: Locator

  constructor(page: Page) {
    this.page = page
    this.addButton = page.locator('[data-testid="add-division-button"]')
    this.table = page.locator('table, [role="table"]')
    this.rows = page.locator('table tbody tr, [role="row"]')
  }

  async goto() {
    await this.page.goto('/divisions')
    await expect(this.table).toBeVisible({ timeout: 5000 })
  }

  async clickAdd() {
    await this.addButton.click()
  }

  async fillName(name: string) {
    await this.page.locator('input[name="name"]').first().fill(name)
  }

  async submit() {
    await this.page.locator('button[type="submit"]').first().click()
  }

  async clickEditOnRow(index = 0) {
    await this.rows.nth(index).locator('[data-testid="edit-division-button"]').click()
  }

  async clickDeleteOnRow(index = 0) {
    await this.rows.nth(index).locator('[data-testid="delete-division-button"]').click()
  }

  async confirmDelete() {
    await this.page.locator('[data-testid="confirm-delete-button"]').click()
  }
}
```

### 4.7 Example E2E Spec

```ts
// e2e/organization/divisions.spec.ts
import { test, expect } from '@playwright/test'
import { DivisionsPage } from '../pages/divisions.page'

const BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:5173'

test.describe('Divisions E2E', () => {
  test.beforeEach(async ({ page }) => {
    await page.context().clearCookies()
    await page.goto(`${BASE_URL}/login`)
    await page.locator('input[type="email"]').first().fill('admin@example.com')
    await page.locator('input[type="password"]').first().fill('changethis')
    await page.locator('button[type="submit"]').first().click()
    await expect(page).toHaveURL(/.*dashboard/, { timeout: 10000 })
  })

  test('should create a new division', async ({ page }) => {
    const divisions = new DivisionsPage(page)
    await divisions.goto()
    await divisions.clickAdd()
    await divisions.fillName('E2E Division')
    await divisions.submit()
    await expect(page.locator('text=/success|created/i')).toBeVisible({ timeout: 5000 })
  })

  test('should edit an existing division', async ({ page }) => {
    const divisions = new DivisionsPage(page)
    await divisions.goto()
    const rowCount = await divisions.rows.count()
    if (rowCount > 0) {
      await divisions.clickEditOnRow(0)
      await divisions.fillName('Updated E2E Division')
      await divisions.submit()
      await expect(page.locator('text=/success|updated/i')).toBeVisible({ timeout: 5000 })
    }
  })

  test('should delete a division', async ({ page }) => {
    const divisions = new DivisionsPage(page)
    await divisions.goto()
    const rowCount = await divisions.rows.count()
    if (rowCount > 0) {
      await divisions.clickDeleteOnRow(0)
      await divisions.confirmDelete()
      await expect(page.locator('text=/success|deleted/i')).toBeVisible({ timeout: 5000 })
    }
  })
})
```

### 4.8 Business Process / User Flow Examples

#### Attendance Flow
1. Login as admin
2. Navigate to **Daily Time Records**
3. Verify table renders with backend data
4. Click **Approve** on a pending overtime row
5. Verify success toast and row status updates
6. Navigate to **DTR Adjustments**
7. Click **New Adjustment**, fill form, submit
8. Verify adjustment appears in list with `pending` status
9. Click **Reject**, verify status changes to `rejected`

#### Leave Flow
1. Login as admin
2. Navigate to **Leave Requests**
3. Click **New Leave Request**, fill form, submit
4. Verify request appears in list with `pending` status
5. Click **Approve**, verify status changes to `approved`
6. Navigate to **Leave Calendar**, verify approved leave appears
7. Navigate to **Leave Ledger**, verify ledger entry was created

#### Organization CRUD Flow
1. Login as admin
2. Navigate to **Divisions**, create a new division
3. Navigate to **Departments**, create a department linked to the division
4. Navigate to **Subdivisions**, create a subdivision linked to the department
5. Verify each created record appears in its respective table
6. Edit each record, verify changes persist
7. Delete each record, verify they are removed

## 5. Implementation Roadmap

### Phase 1: Infrastructure (Week 1)
- [ ] Add `data-testid` attributes to all key interactive elements across features
- [ ] Create `e2e/fixtures/`, `e2e/helpers/`, `e2e/pages/` directories
- [ ] Implement `auth.fixture.ts`, `api.fixture.ts`, and shared `selectors.ts`
- [ ] Create base page objects for: divisions, departments, subdivisions, daily-time-records, leave-requests, dtr-adjustments
- [ ] Configure `globalSetup` / `globalTeardown` in `playwright.config.ts`
- [ ] Add `test:e2e` script to `package.json`

### Phase 2: Critical User Journeys (Week 2)
- [ ] Auth flows: login, logout, token refresh, permission-based access
- [ ] Attendance flows: DTR list, overtime approve/reject, DTR adjustment submit/reject
- [ ] Leave flows: leave request submit/approve, calendar, ledger
- [ ] Organization CRUD: divisions, departments, subdivisions (create → edit → delete)

### Phase 3: Full Feature Coverage (Week 3–4)
- [ ] Projects: projects, phases, blocks, lots, categories, models, model-types, owners
- [ ] Employee management: employee list, profile, CSV import
- [ ] RBAC: roles, permission matrix
- [ ] Dashboard: stats, charts

### Phase 4: CI Integration (Week 5)
- [ ] Add Playwright E2E to GitHub Actions workflow
- [ ] Configure test database seeding for E2E tests
- [ ] Add coverage enforcement gate (`vitest run --coverage --browser.headless` with minimum thresholds)
- [ ] Configure Playwright reporters (HTML + JSON) to publish as CI artifacts

## 6. Coverage Goals

| Layer | Current | Target |
|---|---|---|
| Vitest files | 74 | 100+ (one per feature + form + state test) |
| Vitest tests | 250 | 400+ |
| Playwright specs | 2 | 20+ |
| Playwright tests | ~10 | 100+ |
| Overall feature coverage | ~60% | 90%+ |

## 7. Execution Checklist

Before marking any feature as tested:
- [ ] **Component tests pass:** renders, loading, error, empty, permission gating, actions
- [ ] **Form tests pass:** render, cancel, submit with valid data, mutation pending disables submit
- [ ] **E2E test passes:** full user journey from login through the feature and back
- [ ] **No regressions:** full `vitest run --browser.headless` suite passes
- [ ] **No new lint/type errors:** `npx tsc --noEmit` and `npx eslint .` clean (or only pre-existing warnings)

## 8. Commands Reference

```bash
# Frontend
cd frontendv3

# Install browser dependencies (once per environment)
bash scripts/setup-playwright-libs.sh

# Run component/integration tests
export LD_LIBRARY_PATH="$(pwd)/.playwright-libs/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"
npx vitest run --browser.headless

# Run specific test file
npx vitest run --browser.headless src/features/divisions/index.test.tsx

# Run E2E tests (requires dev server running)
npm run test:e2e

# Type check
npx tsc --noEmit

# Lint
npx eslint .

# Build (also regenerates routeTree.gen.ts)
npm run build
```
