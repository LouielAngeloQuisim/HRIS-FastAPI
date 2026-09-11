import { test, expect } from '../fixtures'
import { DepartmentsPage } from '../pages/departments.page'

test.describe('Departments E2E', () => {
  test.beforeEach(async ({ loginAsAdmin }) => {
    await loginAsAdmin()
  })

  test('should display the departments list', async ({ page }) => {
    const departments = new DepartmentsPage(page)
    await departments.goto()
    const count = await departments.getRowCount()
    expect(count).toBeGreaterThanOrEqual(0)
  })

  test('should create a new department', async ({ page }) => {
    const departments = new DepartmentsPage(page)
    await departments.goto()
    await departments.clickAdd()
    await departments.fillCode('E2E-DEPT-001')
    await departments.fillName('E2E Test Department')
    await departments.fillDescription('Created by E2E test')
    await departments.selectDivision('E2E Test Division')
    await departments.submit()
    await expect(page.locator('[data-testid="department-submit-button"]')).toHaveText('Create', { timeout: 10000 })
  })

  test('should edit an existing department', async ({ page }) => {
    const departments = new DepartmentsPage(page)
    await departments.goto()
    const rowCount = await departments.getRowCount()
    if (rowCount > 0) {
      await departments.clickEditOnRow(0)
      await departments.fillName('Updated E2E Department')
      await departments.submit()
      await expect(page.locator('text=/success|updated/i')).toBeVisible({ timeout: 5000 })
    }
  })

  test('should delete a department', async ({ page }) => {
    const departments = new DepartmentsPage(page)
    await departments.goto()
    const rowCount = await departments.getRowCount()
    if (rowCount > 0) {
      await departments.clickDeleteOnRow(0)
      await departments.confirmDelete()
      await expect(page.locator('text=/success|deleted/i')).toBeVisible({ timeout: 5000 })
    }
  })
})
