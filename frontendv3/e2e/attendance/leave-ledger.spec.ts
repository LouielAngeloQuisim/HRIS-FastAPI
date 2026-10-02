import { test, expect } from '../fixtures'
import { apiUrl, createParent } from '../helpers/crud-journey'
test('ledger requires real employee and policy selections then displays their balance', async ({ page, loginAsAdmin }) => {
 await loginAsAdmin()
 const unique = Date.now().toString(36)
 const employee = await createParent(page, 'employees', { employee_code: 'G' + unique, first_name: 'Ledger', last_name: 'Test', birthdate: '1990-01-01' })
 const policy = await createParent(page, 'leave-policies', { code: 'G' + unique, name: 'Ledger policy', annual_entitlement_days: '15.00', cadence: 'annual' })
 await createParent(page, 'employees/' + employee.id + '/leave-enrollments', { policy_id: policy.id, leave_year: 2026 })
 await page.goto('/leave-ledger')
 await expect(page.getByText('Select an employee to view their leave ledger.')).toBeVisible()
 await expect(page.getByTestId('leave-ledger-refresh-button')).toBeDisabled()
 await expect(page.getByText('Loading...')).not.toBeVisible()
 await page.getByTestId('leave-ledger-year-input').fill('2026')
 await page.getByTestId('leave-ledger-employee-select').selectOption(employee.id)
 await expect(page.getByText('Select a leave policy to view its ledger.')).toBeVisible()
 const load = page.waitForResponse(r => r.url().startsWith(apiUrl) && r.url().includes('/leave-ledger') && r.request().method() === 'GET')
 await page.getByTestId('leave-ledger-policy-select').selectOption(policy.id)
 const response = await load
 expect(response.status()).toBe(200)
 expect(new URL(response.url()).searchParams.get('policy_id')).toBe(policy.id)
 const body = await response.json()
 await expect(page.getByText('Granted: ' + body.summary.granted_total + ' | Consumed: ' + body.summary.consumed_total + ' | Remaining: ' + body.summary.remaining)).toBeVisible()
 await expect(page.getByTestId('leave-ledger-refresh-button')).toBeEnabled()
})
