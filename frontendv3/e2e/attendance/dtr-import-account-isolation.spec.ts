import { test, expect } from '../fixtures'
import { apiUrl, createParent } from '../helpers/crud-journey'

/**
 * PR74 review P1 — cross-account isolation of the recoverable import batch.
 *
 * The in-memory restore slot is bound to the authenticated owner: after a
 * lost-response import leaves rows UNKNOWN and the wizard closes, signing in
 * as a DIFFERENT account must show a clean wizard — the previous account's
 * employee CSV, identity keys and verdicts must never be restored,
 * reconciled or retried by the new one. This is a real SPA logout/login
 * journey (client-side navigation only): a full page reload would reset the
 * in-memory slot and make the isolation assertion vacuous.
 *
 * The server-side data stays untouched: the punch the lost response really
 * committed is verified once through the API and then cleaned up.
 */

const wizardCsv = (code: string) =>
  `employee_code,login_date,logout_date\n${code},2026-10-02T08:00:00Z,2026-10-02T17:00:00Z`

const ADMIN = {
  email: process.env.E2E_ADMIN_EMAIL || 'admin@example.com',
  password: process.env.E2E_ADMIN_PASSWORD || 'e2e-admin-placeholder',
}

async function bearer(page: import('@playwright/test').Page) {
  const token = (await page.context().cookies()).find(c => c.name === 'hris_at')?.value
  if (!token) throw new Error('Missing authenticated test session')
  return token
}

async function rowsForKey(page: import('@playwright/test').Page, key: string) {
  const res = await page.request.get(`${apiUrl}/daily-time-records?limit=1000`, {
    headers: { Authorization: `Bearer ${await bearer(page)}` },
  })
  expect(res.status()).toBe(200)
  const body = await res.json()
  return (body.data || []).filter((r: { source_ref?: string }) => r.source_ref === key)
}

/** Abort the wizard's bare POST /daily-time-records AFTER forwarding it, so
 *  the row really commits but the browser never gets a verdict (UNKNOWN). */
async function lostResponseRoute(page: import('@playwright/test').Page) {
  const captured: { key: string } = { key: '' }
  let fired = false
  await page.route('**/api/v1/daily-time-records', async route => {
    if (route.request().method() !== 'POST' || fired) {
      await route.continue()
      return
    }
    fired = true
    captured.key = JSON.parse(route.request().postData() ?? '{}').source_ref ?? ''
    await route.fetch()
    await route.abort('connectionclosed')
  })
  return captured
}

/** Fill the already-open sign-in form (client-side submit, no reload). */
async function submitSignIn(page: import('@playwright/test').Page, email: string, password: string) {
  await page.getByTestId('login-email-input').fill(email)
  await page.getByTestId('login-password-input').fill(password)
  await page.getByTestId('login-submit-button').click()
}

test.describe('DTR CSV import cross-account isolation E2E (PR74 P1)', () => {
  test('an unresolved batch closed by one account is never restored for another account after SPA logout/login', async ({ page }) => {
    test.setTimeout(120000)
    const unique = Date.now().toString(36)

    // --- Account A (admin) signs in through the SPA -----------------------
    await page.goto('/sign-in')
    await submitSignIn(page, ADMIN.email, ADMIN.password)
    await expect(page).not.toHaveURL(/\/sign-in(\?|$)/, { timeout: 15000 })
    const employee = await createParent(page, 'employees', {
      employee_code: 'QA5' + unique, first_name: 'Isolation', last_name: unique, birthdate: '1990-01-01',
    })

    // --- A: lost-response import -> UNKNOWN -> close (batch stored) -------
    const captured = await lostResponseRoute(page)
    await page.getByRole('link', { name: /daily time records/i }).click()
    await page.getByTestId('import-dtr-csv-button').click()
    await page.getByPlaceholder(/employee_code/).fill(wizardCsv(employee.employee_code))
    await page.getByTestId('csv-import-submit-button').click()
    await expect(page.getByTestId('csv-import-unknown-count')).toBeVisible()
    expect(captured.key).toMatch(/^dtr-import-[a-z0-9]+-r0$/)

    await page.getByTestId('csv-import-close-button').click()
    await expect(page.getByTestId('import-dtr-csv-button')).toBeVisible()

    // Reopen as the SAME account: QA-01 recovery still works (guard that the
    // isolation fix did not break legitimate restore).
    await page.getByTestId('import-dtr-csv-button').click()
    await expect(page.getByTestId('csv-import-restored-banner')).toBeVisible()
    await page.getByTestId('csv-import-close-button').click()
    await expect(page.getByTestId('import-dtr-csv-button')).toBeVisible()

    // --- Create account B (isolated fictional email + placeholder pass) ---
    const userB = { email: `qa-isolation-${unique}@example.com`, password: 'qa-isolation-placeholder' }
    await page.request.post(`${apiUrl}/users`, {
      headers: { Authorization: `Bearer ${await bearer(page)}` },
      data: { email: userB.email, password: userB.password, full_name: 'Isolation B', is_superuser: true },
    }).then(r => expect(r.status(), 'create second E2E account').toBe(201))

    // --- Real SPA logout (client-side): nav-user -> Sign out -> confirm ----
    await page.getByTestId('nav-user-trigger').click()
    await page.getByRole('menuitem', { name: /sign out/i }).click()
    await page.getByTestId('confirm-delete-button').click()
    await page.waitForURL(/\/sign-in/, { timeout: 10000 })

    // --- SPA login as B (no reload); lands back on the DTR page -----------
    await submitSignIn(page, userB.email, userB.password)
    await page.waitForURL(/\/daily-time-records/, { timeout: 15000 })

    // --- B: the wizard must be a CLEAN SLATE -------------------------------
    await page.getByTestId('import-dtr-csv-button').click()
    await expect(page.getByTestId('csv-import-restored-banner')).toHaveCount(0)
    await expect(page.getByTestId('csv-import-unknown-count')).toHaveCount(0)
    await expect(page.getByTestId('csv-import-reconcile-button')).toHaveCount(0)
    // A's CSV text was never handed over: the editor is empty and unlocked.
    await expect(page.getByPlaceholder(/employee_code/)).toHaveValue('')
    await expect(page.getByPlaceholder(/employee_code/)).toBeEnabled()
    await expect(page.getByTestId('csv-import-submit-button')).toBeDisabled()
    await page.getByTestId('csv-import-close-button').click()

    // --- Server-side state untouched by the client isolation --------------
    // B (superuser) sees A's committed punch exactly once; deleting it here
    // also cleans the row up for the suite.
    const rows = await rowsForKey(page, captured.key)
    expect(rows.length).toBe(1)
    await page.request.delete(`${apiUrl}/daily-time-records/${rows[0].id}`, {
      headers: { Authorization: `Bearer ${await bearer(page)}` },
    }).then(r => expect(r.status()).toBe(200))

    // --- Cleanup: log back in as admin and delete account B ---------------
    await page.goto('/sign-in')
    await submitSignIn(page, ADMIN.email, ADMIN.password)
    await expect(page).not.toHaveURL(/\/sign-in(\?|$)/, { timeout: 15000 })
    const list = await page.request.get(`${apiUrl}/users/?limit=500`, {
      headers: { Authorization: `Bearer ${await bearer(page)}` },
    })
    expect(list.status()).toBe(200)
    const b = (await list.json()).data.find((u: { email: string }) => u.email === userB.email)
    if (b) {
      await page.request.delete(`${apiUrl}/users/${b.id}`, {
        headers: { Authorization: `Bearer ${await bearer(page)}` },
      }).then(r => expect(r.status()).toBe(200))
    }
  })
})