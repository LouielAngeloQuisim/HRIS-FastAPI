import { test, expect } from '../fixtures'
import { apiUrl, createParent } from '../helpers/crud-journey'

/**
 * QA-01 — CSV import lost-response / idempotency E2E.
 *
 * The lost-response simulation commits server-side (route.fetch forwards the
 * POST to the REAL backend so the punch is written), THEN aborts the response
 * delivery to the browser — exactly what a real network drop after a server
 * commit looks like. No mock verdicts: Reconcile hits the real reconcile API,
 * and every outcome is verified by reading the database back through the API.
 */

const wizardCsv = (code: string) =>
  `employee_code,login_date,logout_date\n${code},2026-10-02T00:00:00Z,2026-10-02T09:00:00Z`

async function bearer(page: import('@playwright/test').Page) {
  const token = (await page.context().cookies()).find(c => c.name === 'hris_at')?.value
  if (!token) throw new Error('Missing authenticated test session')
  return token
}

async function rowsForKey(page: import('@playwright/test').Page, key: string) {
  const res = await page.request.get(`${apiUrl}/daily-time-records?limit=500`, {
    headers: { Authorization: `Bearer ${await bearer(page)}` },
  })
  expect(res.status()).toBe(200)
  const body = await res.json()
  const rows = body.data || []
  return rows.filter((r: { source_ref?: string }) => r.source_ref === key)
}

async function assignTestShift(page: import('@playwright/test').Page, employeeId: string, code: string) {
  const shift = await createParent(page, 'shifts', {
    code, name: `QA ${code}`, start_time: '08:00', end_time: '17:00',
    lunch_break_duration: 60, total_hours_minus_lunch: 480,
    days_of_week: ['1', '2', '3', '4', '5', '6', '7'],
  })
  const response = await page.request.post(`${apiUrl}/employee-shift-assignments/`, {
    headers: { Authorization: `Bearer ${await bearer(page)}` },
    data: { employee_id: employeeId, shift_id: shift.id, effective_from: '2026-10-02' },
  })
  expect(response.status(), 'assign effective test shift').toBe(201)
}

/** Forward the atomic batch commit, then drop only its response. */
async function lostResponseRoute(page: import('@playwright/test').Page, commit: boolean) {
  const captured: { key: string } = { key: '' }
  let fired = false
  await page.route('**/api/v1/daily-time-records/import-batches/commit', async route => {
    if (route.request().method() !== 'POST' || fired) {
      await route.continue()
      return
    }
    fired = true
    const payload = JSON.parse(route.request().postData() ?? '{}') as { batch_id: string }
    captured.key = `dtr-import-${payload.batch_id}-r0`
    if (commit) {
      // Server writes the row for real, then the delivery to the browser dies.
      await route.fetch()
    }
    await route.abort('connectionclosed')
  })
  return captured
}

test.describe('DTR CSV import idempotency E2E (QA-01)', () => {
  test.beforeEach(async ({ loginAsAdmin }) => {
    await loginAsAdmin()
  })

  test('commit-then-lost-response shows UNKNOWN; server-side Reconcile settles it committed; exactly one row exists; UI delete removes the persisted punch', async ({ page }) => {
    const unique = Date.now().toString(36)
    const employee = await createParent(page, 'employees', { employee_code: 'QA1' + unique, first_name: 'Lost', last_name: unique, birthdate: '1990-01-01' })
    await assignTestShift(page, employee.id, 'QA1' + unique)

    const captured = await lostResponseRoute(page, true)
    await page.goto('/daily-time-records')
    await page.getByTestId('import-dtr-csv-button').click()
    await page.getByPlaceholder(/employee_code/).fill(wizardCsv(employee.employee_code))
    await page.getByTestId('csv-import-submit-button').click()

    // Browser verdict: UNKNOWN — never "failed" (we cannot know it did not commit).
    await expect(page.getByTestId('csv-import-unknown-count')).toBeVisible()
    await expect(page.getByText(/1 unknown/i)).toBeVisible()
    await expect(page.getByText(/No response received/i)).toBeVisible()
    expect(captured.key).toMatch(/^dtr-import-[0-9a-f-]{36}-r0$/i)

    // The real backend DID commit behind the lost response.
    const committed = await rowsForKey(page, captured.key)
    expect(committed.length).toBe(1)

    // Import/retry stays blocked while an identity is unresolved.
    await expect(page.getByTestId('csv-import-submit-button')).toBeDisabled()

    // Reconcile asks the REAL server for a verdict on the (employee, key) pair.
    await page.getByTestId('csv-import-reconcile-button').click()
    await expect(page.getByText(/1 succeeded/i)).toBeVisible()
    // Still exactly one row — reconcile never creates or duplicates anything.
    expect((await rowsForKey(page, captured.key)).length).toBe(1)

    // Close (batch fully resolved) and reopen: clean slate, no restored banner.
    await page.getByTestId('csv-import-close-button').click()
    await expect(page.getByTestId('import-dtr-csv-button')).toBeVisible()
    await page.getByTestId('import-dtr-csv-button').click()
    await expect(page.getByTestId('csv-import-restored-banner')).toHaveCount(0)
    await page.getByTestId('csv-import-close-button').click()

    // The reconciled punch is visible and deletable through the UI.
    const recordId = committed[0].id as string
    await expect(page.getByTestId(`delete-daily-time-record-button-${recordId}`)).toBeVisible({ timeout: 10000 })
    await page.getByTestId(`delete-daily-time-record-button-${recordId}`).click()
    await page.getByRole('alertdialog').getByRole('button', { name: 'Delete', exact: true }).click()
    await expect(page.getByTestId(`delete-daily-time-record-button-${recordId}`)).toHaveCount(0, { timeout: 10000 })
    const gone = await page.request.get(`${apiUrl}/daily-time-records/${recordId}`, {
      headers: { Authorization: `Bearer ${await bearer(page)}` },
    })
    expect(gone.status()).toBe(404)
  })

  test('unresolved identities survive close/reopen: banner restores the batch, edits are blocked, and the SAME key reconciles to the committed row', async ({ page }) => {
    const unique = Date.now().toString(36)
    const employee = await createParent(page, 'employees', { employee_code: 'QA2' + unique, first_name: 'Reopen', last_name: unique, birthdate: '1990-01-01' })
    await assignTestShift(page, employee.id, 'QA2' + unique)

    const captured = await lostResponseRoute(page, true)
    await page.goto('/daily-time-records')
    await page.getByTestId('import-dtr-csv-button').click()
    await page.getByPlaceholder(/employee_code/).fill(wizardCsv(employee.employee_code))
    await page.getByTestId('csv-import-submit-button').click()
    await expect(page.getByText(/1 unknown/i)).toBeVisible()

    // Close while UNKNOWN — the page unmounts the wizard; the batch must survive.
    await page.getByTestId('csv-import-close-button').click()
    await expect(page.getByTestId('import-dtr-csv-button')).toBeVisible()

    // Reopen: recoverable state, editor locked (replacing the CSV here would
    // abandon an identity that may already be committed server-side).
    await page.getByTestId('import-dtr-csv-button').click()
    await expect(page.getByTestId('csv-import-restored-banner')).toBeVisible()
    await expect(page.getByText(/1 unknown/i)).toBeVisible()
    await expect(page.getByPlaceholder(/employee_code/)).toBeDisabled()
    await expect(page.getByTestId('csv-import-submit-button')).toBeDisabled()

    // Reconcile on the restored batch uses the ORIGINAL key — the real server
    // matches the row the lost response committed and settles it committed.
    await page.getByTestId('csv-import-reconcile-button').click()
    await expect(page.getByText(/1 succeeded/i)).toBeVisible()
    expect((await rowsForKey(page, captured.key)).length).toBe(1)
    await page.getByTestId('csv-import-close-button').click()
  })

  test('never-reached request reconciles to not_found, key-stable retry commits exactly one row, then Discard path unlocks fresh import', async ({ page }) => {
    const unique = Date.now().toString(36)
    const employee = await createParent(page, 'employees', { employee_code: 'QA3' + unique, first_name: 'Retry', last_name: unique, birthdate: '1990-01-01' })
    await assignTestShift(page, employee.id, 'QA3' + unique)

    // Abort BEFORE forwarding: nothing is committed anywhere.
    const captured = await lostResponseRoute(page, false)
    await page.goto('/daily-time-records')
    await page.getByTestId('import-dtr-csv-button').click()
    await page.getByPlaceholder(/employee_code/).fill(wizardCsv(employee.employee_code))
    await page.getByTestId('csv-import-submit-button').click()
    await expect(page.getByText(/1 unknown/i)).toBeVisible()

    // Server verdict: not_found within scope -> retry is safe, but the retry
    // MUST reuse the same key so a hypothetical late commit cannot duplicate.
    await page.getByTestId('csv-import-reconcile-button').click()
    await expect(page.getByTestId('csv-correction-row-2').getByText(/retry is safe/i)).toBeVisible()
    await expect(page.getByTestId('csv-import-submit-button')).toBeEnabled()
    expect(await rowsForKey(page, captured.key)).toHaveLength(0)

    await page.getByTestId('csv-import-submit-button').click()
    await expect(page.getByText(/1 succeeded/i)).toBeVisible()
    const rows = await rowsForKey(page, captured.key)
    expect(rows.length).toBe(1)
    expect(rows[0].id).toBeTruthy()

    await page.getByTestId('csv-import-close-button').click()
  })

  test('Discard explicitly abandons unresolved identities and unlocks the editor', async ({ page }) => {
    const unique = Date.now().toString(36)
    const employee = await createParent(page, 'employees', { employee_code: 'QA4' + unique, first_name: 'Discard', last_name: unique, birthdate: '1990-01-01' })
    await assignTestShift(page, employee.id, 'QA4' + unique)

    await lostResponseRoute(page, false)
    await page.goto('/daily-time-records')
    await page.getByTestId('import-dtr-csv-button').click()
    await page.getByPlaceholder(/employee_code/).fill(wizardCsv(employee.employee_code))
    await page.getByTestId('csv-import-submit-button').click()
    await expect(page.getByText(/1 unknown/i)).toBeVisible()

    await page.getByTestId('csv-import-discard-button').click()
    await expect(page.getByText(/1 unknown/i)).toHaveCount(0)
    await expect(page.getByPlaceholder(/employee_code/)).toBeEnabled()
    await page.getByTestId('csv-import-close-button').click()
  })
})
