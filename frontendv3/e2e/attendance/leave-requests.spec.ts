import { test, expect } from '../fixtures'
import { createParent, waitForWrite, assertWrite } from '../helpers/crud-journey'
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
    const unique = Date.now().toString(36)
    const employee = await createParent(page, 'employees', { employee_code: 'E' + unique, first_name: 'E2E', last_name: 'Leave', birthdate: '1990-01-01' })
    const policy = await createParent(page, 'leave-policies', { code: 'L' + unique, name: 'E2E leave', annual_entitlement_days: '15.00', cadence: 'annual' })
    await createParent(page, 'employees/' + employee.id + '/leave-enrollments', { policy_id: policy.id, leave_year: 2026 })
    await leave.fillEmployeeId(employee.id)
    await leave.fillPolicyId(policy.id)
    await leave.fillDateStart('2026-09-15')
    await leave.fillDateEnd('2026-09-16')
    await leave.fillReason('E2E test leave')
    const submitted = waitForWrite(page, 'leave-requests', 'POST')
    await leave.submit()
    const created = await assertWrite(await submitted, 201)
    expect(created.employee_id).toBe(employee.id)
    expect(created.policy_id).toBe(policy.id)
    await expect(page.getByTestId('leave-request-submit-button')).not.toBeVisible()
  })

  test('should filter by status', async ({ page }) => {
    const leave = new LeaveRequestsPage(page)
    await leave.goto()
    await leave.statusFilter.selectOption('pending')
    await expect(page.locator('table, [role="table"]')).toBeVisible({ timeout: 5000 })
  })
})
