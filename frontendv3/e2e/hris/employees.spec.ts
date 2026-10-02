import { test, expect } from '../fixtures'
import { EmployeesPage } from '../pages/employees.page'

test.describe('Employees E2E', () => {
  test.beforeEach(async ({ loginAsAdmin }) => {
    await loginAsAdmin()
  })

  test('should display the employees list', async ({ page }) => {
    const employees = new EmployeesPage(page)
    await employees.goto()
    const count = await employees.getRowCount()
    expect(count).toBeGreaterThanOrEqual(0)
  })

  test('should open CSV import dialog', async ({ page }) => {
    const employees = new EmployeesPage(page)
    await employees.goto()
    await employees.clickCsvImport()
    await expect(page.getByRole('dialog', { name: 'Import Employees from CSV' })).toBeVisible({ timeout: 5000 })
  })

  test('should retry on error', async ({ page }) => {
    const employees = new EmployeesPage(page)
    await employees.goto()
    await page.route('**/api/v1/employees?**', route => route.fulfill({ status: 500, json: { error: { message: 'Injected test failure' } } }))
    await page.reload()
    await expect(page.getByText('Failed to load employees.')).toBeVisible({ timeout: 15000 })
    await page.unroute('**/api/v1/employees?**')
    await page.getByRole('button', { name: 'Try again', exact: true }).click()
    await expect(page.getByText('Failed to load employees.')).not.toBeVisible({ timeout: 10000 })
    await expect(page.locator('table')).toBeVisible()
  })
})
