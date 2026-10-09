import { test, expect } from '../fixtures'
import { apiUrl, assignEmployeeShift, createParent } from '../helpers/crud-journey'

/**
 * QA-03 — DTR adjustment approval flow end-to-end.
 *
 * The server sends uppercase statuses (PENDING/APPROVED/REJECTED). The list
 * only renders approve/reject for PENDING and must never show stale action
 * buttons after approval. Approval must persist across a full reload and
 * recompute the DTR (server-authoritative); rejection must leave the DTR
 * untouched. Verified via API readback, not just UI text.
 */

async function bearer(page: import('@playwright/test').Page) {
  const token = (await page.context().cookies()).find(c => c.name === 'hris_at')?.value
  if (!token) throw new Error('Missing authenticated test session')
  return token
}

async function getJson(page: import('@playwright/test').Page, path: string) {
  const res = await page.request.get(`${apiUrl}${path}`, {
    headers: { Authorization: `Bearer ${await bearer(page)}` },
  })
  expect(res.status()).toBe(200)
  return res.json()
}

async function createAdjustmentThroughUi(page: import('@playwright/test').Page, employeeCode: string, dtrId: string, adjustedLogout: string) {
  await page.getByTestId('new-dtr-adjustment-button').click()
  await page.getByTestId('dtr-adjustment-dtr-select').click()
  await page.getByRole('option').filter({ hasText: employeeCode }).click()
  await page.getByTestId('dtr-adjustment-date-input').fill('2026-09-15')
  await page.getByTestId('dtr-adjustment-login-input').fill('2026-09-15T08:00')
  await page.getByTestId('dtr-adjustment-logout-input').fill(adjustedLogout)
  await page.getByTestId('dtr-adjustment-reason-input').fill('E2E QA-03')
  const created = page.waitForResponse(r =>
    r.status() !== 307 && r.request().method() === 'POST' && new URL(r.url()).pathname.replace(/\/$/, '') === '/api/v1/dtr-adjustments'
  )
  await page.getByTestId('dtr-adjustment-submit-button').click()
  const res = await created
  expect(res.status()).toBe(201)
  const body = await res.json()
  expect((body.data || body).daily_time_record_id).toBe(dtrId)
  return body.data || body
}

test.describe('DTR adjustment approval E2E (QA-03)', () => {
  test.beforeEach(async ({ loginAsAdmin }) => {
    await loginAsAdmin()
  })

  test('approve persists uppercase APPROVED across reload, recomputes the DTR, and removes the action buttons', async ({ page }) => {
    const unique = Date.now().toString(36)
    const employee = await createParent(page, 'employees', { employee_code: 'AD' + unique, first_name: 'Approve', last_name: unique, birthdate: '1990-01-01' })
    await assignEmployeeShift(page, employee.id)
    const dtr = await createParent(page, 'daily-time-records', { employee_id: employee.id, login_date: '2026-09-15T08:00:00', logout_date: '2026-09-15T17:00:00' })

    const adjustment = await page.goto('/dtr-adjustments').then(async () => {
      await expect(page.getByTestId('new-dtr-adjustment-button')).toBeVisible()
      return createAdjustmentThroughUi(page, employee.employee_code, dtr.id, '2026-09-15T16:30')
    })
    expect(adjustment.status).toBe('PENDING')

    // QA-03 core: uppercase PENDING renders the row actions.
    await expect(page.getByTestId(`approve-dtr-adjustment-button-${adjustment.id}`)).toBeVisible()

    await page.getByTestId(`approve-dtr-adjustment-button-${adjustment.id}`).click()
    await expect(page.getByTestId(`approve-dtr-adjustment-button-${adjustment.id}`)).toHaveCount(0, { timeout: 10000 })

    // Authoritative readback: server persisted the uppercase status.
    const afterApprove = await getJson(page, `/dtr-adjustments/${adjustment.id}`)
    expect(afterApprove.data?.status ?? afterApprove.status).toBe('APPROVED')

    // Approval recomputed the DTR with the adjusted logout.
    const dtrAfter = await getJson(page, `/daily-time-records/${dtr.id}`)
    const dtrBody = dtrAfter.data || dtrAfter
    expect(dtrBody.logout_date).toContain('16:30:00')

    // Full reload: status stays APPROVED and no stale action buttons reappear.
    await page.reload()
    await expect(page.getByTestId(`approve-dtr-adjustment-button-${adjustment.id}`)).toHaveCount(0)
    await expect(page.getByRole('cell', { name: 'APPROVED', exact: true }).first()).toBeVisible()
  })

  test('reject persists uppercase REJECTED across reload and leaves the DTR unchanged', async ({ page }) => {
    const unique = Date.now().toString(36)
    const employee = await createParent(page, 'employees', { employee_code: 'RD' + unique, first_name: 'Reject', last_name: unique, birthdate: '1990-01-01' })
    await assignEmployeeShift(page, employee.id)
    const dtr = await createParent(page, 'daily-time-records', { employee_id: employee.id, login_date: '2026-09-15T08:00:00', logout_date: '2026-09-15T17:00:00' })

    await page.goto('/dtr-adjustments')
    await expect(page.getByTestId('new-dtr-adjustment-button')).toBeVisible()
    const adjustment = await createAdjustmentThroughUi(page, employee.employee_code, dtr.id, '2026-09-15T18:00')

    await page.getByTestId(`reject-dtr-adjustment-button-${adjustment.id}`).click()
    await expect(page.getByTestId(`reject-dtr-adjustment-button-${adjustment.id}`)).toHaveCount(0, { timeout: 10000 })

    const afterReject = await getJson(page, `/dtr-adjustments/${adjustment.id}`)
    expect((afterReject.data || afterReject).status).toBe('REJECTED')

    // Rejection must NOT apply the adjusted times.
    const dtrAfter = await getJson(page, `/daily-time-records/${dtr.id}`)
    expect((dtrAfter.data || dtrAfter).logout_date).toContain('17:00:00')

    await page.reload()
    await expect(page.getByTestId(`approve-dtr-adjustment-button-${adjustment.id}`)).toHaveCount(0)
    await expect(page.getByRole('cell', { name: 'REJECTED', exact: true }).first()).toBeVisible()
  })
})
