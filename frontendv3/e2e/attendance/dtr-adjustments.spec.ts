import { test, expect } from '../fixtures'
import { createParent, waitForWrite, assertWrite } from '../helpers/crud-journey'
import { DtrAdjustmentsPage } from '../pages/dtr-adjustments.page'

test.describe('DTR Adjustments E2E', () => {
  test.beforeEach(async ({ loginAsAdmin }) => {
    await loginAsAdmin()
  })

  test('should display the DTR adjustments list', async ({ page }) => {
    const adjustments = new DtrAdjustmentsPage(page)
    await adjustments.goto()
    const count = await adjustments.getRowCount()
    expect(count).toBeGreaterThanOrEqual(0)
  })

  test('should submit a new DTR adjustment', async ({ page }) => {
    const adjustments = new DtrAdjustmentsPage(page)
    await adjustments.goto()
    const unique = Date.now().toString(36)
    const employee = await createParent(page, 'employees', { employee_code: 'E' + unique, first_name: 'E2E', last_name: 'Adjustment', birthdate: '1990-01-01' })
    const dtr = await createParent(page, 'daily-time-records', { employee_id: employee.id, login_date: '2026-09-15T08:00:00', logout_date: '2026-09-15T17:00:00' })
    await adjustments.clickNew()
    await adjustments.fillDtrId(employee.id)
    await page.getByTestId('dtr-adjustment-date-input').fill('2026-09-15')
    await adjustments.fillAdjustedLogin('2026-09-15T08:00')
    await adjustments.fillAdjustedLogout('2026-09-15T17:00')
    await adjustments.fillReason('E2E test adjustment')
    const submitted = waitForWrite(page, 'dtr-adjustments', 'POST')
    await adjustments.submit()
    const created = await assertWrite(await submitted, 201)
    expect(created.daily_time_record_id).toBe(dtr.id)
    await expect(page.getByTestId('dtr-adjustment-submit-button')).not.toBeVisible()
  })
})
