import { test, expect } from '../fixtures'
import { apiUrl, assignEmployeeShift, createParent } from '../helpers/crud-journey'

/**
 * QA-08 — Dashboard daily attendance KPI (Asia/Manila, distinct employees).
 *
 * The KPI counts DISTINCT employees with >=1 real punch in the Asia/Manila
 * calendar day containing "now" — legacy bug counted raw rows and used a
 * broken day window. Verified with deltas so shared test data cannot flake:
 *   punch for new employee            -> +1
 *   second work interval, same DTR    -> unchanged (one daily record)
 *   remove one interval               -> unchanged (employee still punched)
 *   delete the daily record           -> back to baseline
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

  test('counts distinct employees punched-in today (Manila), tolerant to multiple intervals and deletions', async ({ page }) => {
    const unique = Date.now().toString(36)
    await page.goto('/')
    await expect(page.getByTestId('kpi-dtr_records_daily_count')).toBeVisible()
    const baseline = await dailyKpi(page)

    // Employee A: first punch of "today" -> distinct count must rise by one.
    const empA = await createParent(page, 'employees', { employee_code: 'KA' + unique, first_name: 'Kpi', last_name: 'A', birthdate: '1990-01-01' })
    await assignEmployeeShift(page, empA.id)
    const pA1 = await punch(page, empA.id)
    expect(await dailyKpi(page)).toBe(baseline + 1)

    // A second work interval belongs to the same employee/work-date DTR.
    const manilaDate = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Manila' }).format(new Date())
    const intervalStart = new Date(`${manilaDate}T08:00:00+08:00`)
    const firstEnd = new Date(`${manilaDate}T08:30:00+08:00`)
    const secondStart = new Date(`${manilaDate}T09:00:00+08:00`)
    const secondEnd = new Date(`${manilaDate}T09:30:00+08:00`)
    const intervalUrl = `${apiUrl}/daily-time-records/${pA1.id}/intervals`
    const authHeaders = { Authorization: `Bearer ${await bearer(page)}` }
    const twoIntervals = await page.request.put(intervalUrl, {
      headers: authHeaders,
      data: { intervals: [
        { start_at: intervalStart.toISOString(), end_at: firstEnd.toISOString() },
        { start_at: secondStart.toISOString(), end_at: secondEnd.toISOString() },
      ] },
    })
    expect(twoIntervals.status()).toBe(200)
    expect(await dailyKpi(page)).toBe(baseline + 1)

    // Employee B punches -> +1 more.
    const empB = await createParent(page, 'employees', { employee_code: 'KB' + unique, first_name: 'Kpi', last_name: 'B', birthdate: '1990-01-01' })
    await assignEmployeeShift(page, empB.id)
    const pB1 = await punch(page, empB.id)
    expect(await dailyKpi(page)).toBe(baseline + 2)

    // Remove one interval: the daily record still represents a punch today.
    const oneInterval = await page.request.put(intervalUrl, {
      headers: authHeaders,
      data: { intervals: [{ start_at: intervalStart.toISOString(), end_at: firstEnd.toISOString() }] },
    })
    expect(oneInterval.status()).toBe(200)
    expect(await dailyKpi(page)).toBe(baseline + 2)

    // Delete A's one daily record and B's punch -> employees leave today's set.
    await page.request.delete(`${apiUrl}/daily-time-records/${pA1.id}`, { headers: authHeaders })
    await page.request.delete(`${apiUrl}/daily-time-records/${pB1.id}`, { headers: authHeaders })
    expect(await dailyKpi(page)).toBe(baseline)
  })
})
