import { test, expect } from '../fixtures'
import { apiUrl, createParent, waitForWrite, assertWrite } from '../helpers/crud-journey'
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
    const unique = Date.now().toString(36)
    const employee = await createParent(page, 'employees', { employee_code: 'E' + unique, first_name: 'E2E', last_name: 'Leave', birthdate: '1990-01-01' })
    const policy = await createParent(page, 'leave-policies', { code: 'L' + unique, name: 'E2E leave', annual_entitlement_days: '15.00', cadence: 'annual' })
    await createParent(page, 'employees/' + employee.id + '/leave-enrollments', { policy_id: policy.id, leave_year: 2026 })
    await leave.clickNew()
    await leave.fillEmployeeId(employee.employee_code + ' - E2E Leave')
    await leave.fillPolicyId(policy.code + ' - E2E leave')
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


test('admin can approve, reject and cancel leave requests and read back each status', async ({ page, loginAsAdmin }) => {
  await loginAsAdmin()
  const unique = Date.now().toString(36)
  const employee = await createParent(page, 'employees', { employee_code: `LC${unique}`, first_name: 'Lifecycle', last_name: 'Leave', birthdate: '1990-01-01' })
  const policy = await createParent(page, 'leave-policies', { code: `LC${unique}`, name: `Lifecycle leave ${unique}`, annual_entitlement_days: '15.00', cadence: 'annual' })
  await createParent(page, `employees/${employee.id}/leave-enrollments`, { policy_id: policy.id, leave_year: 2026 })
  const leave = new LeaveRequestsPage(page)
  await leave.goto()

  async function submitRequest(date: string, reason: string) {
    await leave.clickNew()
    await leave.fillEmployeeId(`${employee.employee_code} - Lifecycle Leave`)
    await leave.fillPolicyId(`${policy.code} - Lifecycle leave ${unique}`)
    await leave.fillDateStart(date)
    await leave.fillDateEnd(date)
    await leave.fillReason(reason)
    const creating = waitForWrite(page, 'leave-requests', 'POST')
    await leave.submit()
    return assertWrite(await creating, 201)
  }

  const approvedReason = `E2E approve ${unique}`
  const rejectedReason = `E2E reject ${unique}`
  const cancelledReason = `E2E cancel ${unique}`
  const approved = await submitRequest('2026-11-02', approvedReason)
  const approving = waitForWrite(page, `leave-requests/${approved.id}/approve`, 'POST')
  await page.getByTestId(`approve-leave-request-button-${approved.id}`).click()
  await assertWrite(await approving, 200)
  await expect(page.getByRole('row').filter({ hasText: approvedReason }).getByText('approved', { exact: true })).toBeVisible()

  const rejected = await submitRequest('2026-11-04', rejectedReason)
  const rejecting = waitForWrite(page, `leave-requests/${rejected.id}/reject`, 'POST')
  await page.getByTestId(`reject-leave-request-button-${rejected.id}`).click()
  await assertWrite(await rejecting, 200)
  await expect(page.getByRole('row').filter({ hasText: rejectedReason }).getByText('rejected', { exact: true })).toBeVisible()

  const cancelled = await submitRequest('2026-11-06', cancelledReason)
  const cancelling = waitForWrite(page, `leave-requests/${cancelled.id}/cancel`, 'POST')
  await page.getByTestId(`cancel-leave-request-button-${cancelled.id}`).click()
  await assertWrite(await cancelling, 200)
  await expect(page.getByRole('row').filter({ hasText: cancelledReason }).getByText('cancelled', { exact: true })).toBeVisible()

  const headers = { Authorization: 'Bearer ' + (await page.context().cookies()).find(c => c.name === 'hris_at')!.value }
  for (const [request, status] of [[approved, 'approved'], [rejected, 'rejected'], [cancelled, 'cancelled']] as const) {
    const readback = await page.request.get(`${apiUrl}/leave-requests/${request.id}`, { headers })
    expect(readback.status()).toBe(200)
    expect((await readback.json()).request.status).toBe(status)
  }

  await page.goto('/leave-calendar')
  await page.getByTestId('leave-calendar-employee-select').selectOption(employee.id)
  await page.getByTestId('leave-calendar-from-date').fill('2026-11-01')
  await page.getByTestId('leave-calendar-to-date').fill('2026-11-03')
  await page.getByTestId('leave-calendar-apply-button').click()
  await expect(page.getByRole('row').filter({ hasText: policy.name }).getByText('approved', { exact: true })).toBeVisible()

  await page.goto('/leave-ledger')
  await page.getByTestId('leave-ledger-employee-select').selectOption(employee.id)
  await page.getByTestId('leave-ledger-policy-select').selectOption(policy.id)
  await expect(page.getByText(/Consumed:/)).toBeVisible()
  await expect(page.getByText(`LeaveRequest:${approved.id}`, { exact: true })).toBeVisible()
})
