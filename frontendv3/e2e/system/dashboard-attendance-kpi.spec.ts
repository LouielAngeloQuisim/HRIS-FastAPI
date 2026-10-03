import { test, expect } from '../fixtures'
import { apiUrl, createParent } from '../helpers/crud-journey'

/**
 * QA-08 — Dashboard daily attendance KPI (Asia/Manila, distinct employees).
 *
 * The KPI counts DISTINCT employees with >=1 real punch in the Asia/Manila
 * calendar day containing "now" — legacy bug counted raw rows and used a
 * broken day window. Verified with deltas so shared test data cannot flake:
 *   punch for new employee            -> +1
 *   second punch, same employee       -> unchanged (distinct, not rows)
 *   delete one of the two             -> unchanged (employee still punched)
 *   delete the last punch of employee -> back to baseline
 */

async function bearer(page: import('@playwright/test').Page) {
  const token = (await page.context().cookies()).find(c => c.name === 'hris_at')?.value
  if (!token) throw new Error('Missing authenticated test session')
  return token
}

async function punch(page: import('@playwright/test').Page, employeeId: string, loginOffsetMs = 0) {
  // login_date NOW (plus optional small offset) is always inside the current
  // Manila calendar day regardless of wall clock; logout only needs to be after.
  const login = new Date(Date.now() + loginOffsetMs)
  return createParent(page, 'daily-time-records', {
    employee_id: employeeId,
    login_date: login.toISOString(),
    logout_date: new Date(login.getTime() + 60 * 60_000).toISOString(),
  })
}

async function dailyKpi(page: import('@playwright/test').Page): Promise<number> {
  await page.reload()
  const tile = page.getByTestId('kpi-dtr_records_daily_count')
  await expect(tile).toBeVisible()
  const raw = (await tile.textContent())?.trim() ?? ''
  const value = Number.parseInt(raw.replace(/\D/g, ''), 10)
  expect(Number.isFinite(value)).toBe(true)
  return value
}

test.describe('Dashboard daily attendance KPI E2E (QA-08)', () => {
  test.beforeEach(async ({ loginAsAdmin }) => {
    await loginAsAdmin()
  })

  test('counts distinct employees punched-in today (Manila), tolerant to second punches and deletions', async ({ page }) => {
    const unique = Date.now().toString(36)
    await page.goto('/')
    await expect(page.getByTestId('kpi-dtr_records_daily_count')).toBeVisible()
    const baseline = await dailyKpi(page)

    // Employee A: first punch of "today" -> distinct count must rise by one.
    const empA = await createParent(page, 'employees', { employee_code: 'KA' + unique, first_name: 'Kpi', last_name: 'A', birthdate: '1990-01-01' })
    const pA1 = await punch(page, empA.id)
    expect(await dailyKpi(page)).toBe(baseline + 1)

    // Employee A punches again the same day -> DISTINCT employee count holds.
    const pA2 = await punch(page, empA.id, 60_000)
    expect(await dailyKpi(page)).toBe(baseline + 1)

    // Employee B punches -> +1 more.
    const empB = await createParent(page, 'employees', { employee_code: 'KB' + unique, first_name: 'Kpi', last_name: 'B', birthdate: '1990-01-01' })
    const pB1 = await punch(page, empB.id)
    expect(await dailyKpi(page)).toBe(baseline + 2)

    // Delete one of A's two punches: A still punched today -> unchanged.
    const del = await page.request.delete(`${apiUrl}/daily-time-records/${pA1.id}`, {
      headers: { Authorization: `Bearer ${await bearer(page)}` },
    })
    expect(del.status()).toBe(200)
    expect(await dailyKpi(page)).toBe(baseline + 2)

    // Delete A's remaining punch and B's punch -> employees leave today's set.
    await page.request.delete(`${apiUrl}/daily-time-records/${pA2.id}`, { headers: { Authorization: `Bearer ${await bearer(page)}` } })
    await page.request.delete(`${apiUrl}/daily-time-records/${pB1.id}`, { headers: { Authorization: `Bearer ${await bearer(page)}` } })
    expect(await dailyKpi(page)).toBe(baseline)
  })
})
