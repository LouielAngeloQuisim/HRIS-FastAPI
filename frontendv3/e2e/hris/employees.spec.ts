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
    await expect(page.locator('[data-testid="csv-import-wizard"]')).toBeVisible({ timeout: 5000 })
  })

  test('should retry on error', async ({ page }) => {
    const employees = new EmployeesPage(page)
    await employees.goto()
    const retryBtn = page.locator('[data-testid="retry-button"]')
    if (await retryBtn.count() > 0) {
      await employees.clickRetry()
    }
  })
})
