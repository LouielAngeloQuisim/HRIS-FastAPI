import { expect, test } from '../fixtures'
import { apiUrl, createParent } from '../helpers/crud-journey'
import type { Page } from '@playwright/test'

async function headers(page: Page) {
  const token = (await page.context().cookies()).find(
    (cookie) => cookie.name === 'hris_at'
  )?.value
  if (!token) throw new Error('Missing isolated QA session')
  return { Authorization: `Bearer ${token}` }
}

test('bulk pay-group assignment preflights, saves explicitly selected employees and persists', async ({
  page,
  loginAsAdmin,
}) => {
  await loginAsAdmin()
  const unique = Date.now().toString(36)
  const employee = await createParent(page, 'employees', {
    employee_code: `PG${unique}`,
    first_name: 'QA Pay Group',
    last_name: unique,
    birthdate: '1990-01-01',
    date_hired: '2026-01-01',
  })
  const groupResponse = await page.request.post(`${apiUrl}/payroll/pay-groups`, {
    headers: await headers(page),
    data: {
      code: `PG${unique}`,
      name: `QA monthly group ${unique}`,
      cadence: 'monthly',
      payment_offset_days: 0,
      weekend_rule: 'next_business_day',
    },
  })
  expect(groupResponse.status(), await groupResponse.text()).toBe(201)
  const group = await groupResponse.json()

  await page.goto('/payroll/salary')
  await expect(page.getByRole('heading', { name: 'Employee Salaries' })).toBeVisible()
  await expect(page.getByLabel(`Assign ${employee.employee_code}`)).toBeVisible()
  await page.getByTestId('bulk-pay-group-select').click()
  await page.getByRole('option', { name: new RegExp(group.name) }).click()
  await page.getByLabel('Pay-group effective date').fill('2028-01-02')
  await page.getByLabel(`Assign ${employee.employee_code}`).check()

  await page.getByTestId('pay-group-bulk-preflight').click()
  await expect(page.getByRole('alert')).toContainText(/start of a pay period/i)
  await expect(page.getByTestId('pay-group-bulk-commit')).toBeDisabled()

  await page.getByLabel('Pay-group effective date').fill('2028-01-01')
  await page.getByTestId('pay-group-bulk-preflight').click()
  await expect(page.getByTestId('pay-group-bulk-commit')).toBeEnabled()
  await page.getByTestId('pay-group-bulk-commit').click()

  await expect(page.getByText(/1 employees assigned/i)).toBeVisible()
  const saved = await page.request.get(
    `${apiUrl}/payroll/pay-group-assignments?employee_id=${employee.id}`,
    { headers: await headers(page) }
  )
  expect(saved.status()).toBe(200)
  expect(await saved.json()).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        employee_id: employee.id,
        pay_group_id: group.id,
        effective_from: '2028-01-01',
        effective_to: null,
      }),
    ])
  )
})
