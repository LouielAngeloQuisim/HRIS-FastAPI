import { test, expect } from '../fixtures'
import { apiUrl, createParent } from '../helpers/crud-journey'
test('calendar selects a real employee and sends changed dates', async ({ page, loginAsAdmin }) => {
 await loginAsAdmin()
 const employee = await createParent(page, 'employees', { employee_code: 'C' + Date.now().toString(36), first_name: 'Calendar', last_name: 'Test', birthdate: '1990-01-01' })
 await page.goto('/leave-calendar')
 await expect(page.getByText('Select an employee to view leave events.')).toBeVisible()
 await expect(page.getByTestId('leave-calendar-apply-button')).toBeDisabled()
 const load = page.waitForResponse(r => r.url().startsWith(apiUrl) && r.url().includes('/leave-calendar') && r.request().method() === 'GET')
 await page.getByTestId('leave-calendar-employee-select').selectOption(employee.id)
 const response = await load
 expect(response.status()).toBe(200)
 expect(new URL(response.url()).pathname).toContain('/employees/' + employee.id + '/leave-calendar')
 await page.getByTestId('leave-calendar-from-date').fill('2026-01-01')
 const filtered = page.waitForResponse(r => r.url().startsWith(apiUrl) && r.url().includes('/leave-calendar') && new URL(r.url()).searchParams.get('to_date') === '2026-12-31')
 await page.getByTestId('leave-calendar-to-date').fill('2026-12-31')
 expect((await filtered).status()).toBe(200)
 await expect(page.getByTestId('leave-calendar-from-date')).toHaveValue('2026-01-01')
})
