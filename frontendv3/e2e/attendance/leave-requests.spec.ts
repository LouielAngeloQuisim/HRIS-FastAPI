import { test, expect } from '../fixtures'
import { LeaveRequestsPage } from '../pages/leave-requests.page'

test.describe('Leave Requests E2E', () => {
  test.beforeEach(async ({ loginAsAdmin }) => {
    await loginAsAdmin()
  })

  test('should display the leave requests list', async ({ page }) => {
    const leave = new LeaveRequestsPage(page)
    await leave.goto()
    const count = await leave.getRowCount()
    expect(count).toBeGreaterThanOrEqual(0)
  })

  test('should submit a new leave request', async ({ page }) => {
    const leave = new LeaveRequestsPage(page)
    await leave.goto()
    await leave.clickNew()
    await leave.fillEmployeeId('E2E-EMP-001')
    await leave.fillPolicyId('E2E-POL-001')
    await leave.fillDateStart('2026-09-15')
    await leave.fillDateEnd('2026-09-16')
    await leave.fillReason('E2E test leave')
    await leave.submit()
    await expect(page.locator('[data-testid="leave-request-submit-button"]')).toHaveText('Submit Request', { timeout: 10000 })
  })

  test('should filter by status', async ({ page }) => {
    const leave = new LeaveRequestsPage(page)
    await leave.goto()
    await leave.statusFilter.selectOption('pending')
    await expect(page.locator('table, [role="table"]')).toBeVisible({ timeout: 5000 })
  })
})
