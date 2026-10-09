import { expect, test } from '../fixtures'
import { apiUrl, createParent } from '../helpers/crud-journey'
import type { Page } from '@playwright/test'

async function authHeaders(page: Page) {
  const token = (await page.context().cookies()).find(
    cookie => cookie.name === 'hris_at'
  )?.value
  if (!token) throw new Error('Missing isolated QA session')
  return { Authorization: `Bearer ${token}` }
}

test('previews and applies a selected salary increment with persisted history', async ({ page, loginAsAdmin }) => {
  await loginAsAdmin()
  const unique = Date.now().toString(36)
  const employee = await createParent(page, 'employees', {
    employee_code: `INC${unique}`,
    first_name: 'Increment',
    last_name: 'Fixture',
    birthdate: '1990-01-01',
    date_hired: '2026-01-01',
  })
  const headers = await authHeaders(page)
  const createdSalary = await page.request.post(
    `${apiUrl}/payroll/employees/${employee.id}/salary`,
    {
      headers,
      data: {
        employee_id: employee.id,
        basic_rate: '15000.00',
        currency: 'PHP',
        effective_date: '2026-01-01',
        pay_type: 'monthly',
        overtime_rate: '100.000',
        absent_penalty_rate: '0.000',
        non_taxable_allowance: '500.00',
        de_minimis_monthly: {},
        thirteenth_month_exempt_portion: '90000.00',
        is_active: true,
      },
    }
  )
  expect(createdSalary.status(), await createdSalary.text()).toBe(200)

  await page.goto('/payroll/salary')
  await expect(page.getByRole('heading', { name: 'Employee Salaries' })).toBeVisible()
  await page.getByLabel('Salary increment employee search').fill(employee.employee_code)
  await page.getByTestId('salary-increment-search').click()
  await page.getByLabel(`Select ${employee.employee_code} for increase`).check()
  await page.getByLabel('Salary increase amount').fill('50.00')
  await page.getByLabel('Salary increase effective date').fill('2028-01-01')
  await page.getByTestId('salary-increment-preview').click()
  await expect(page.getByText(new RegExp(`${employee.employee_code} — Increment Fixture: ₱15000\\.00 → ₱15050\\.00`))).toBeVisible()
  await page.getByTestId('salary-increment-commit').click()
  await expect(page.getByText(/1 salary increments saved/i)).toBeVisible()

  const history = await page.request.get(
    `${apiUrl}/payroll/employees/${employee.id}/salary`,
    { headers }
  )
  expect(history.status()).toBe(200)
  expect(await history.json()).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        basic_rate: '15000.00',
        effective_date: '2026-01-01',
      }),
      expect.objectContaining({
        basic_rate: '15050.00',
        effective_date: '2028-01-01',
        overtime_rate: '100.000',
        non_taxable_allowance: '500.00',
      }),
    ])
  )
})
