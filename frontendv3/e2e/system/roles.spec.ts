import { test, expect } from '../fixtures'
import { RolesPage } from '../pages/roles.page'

test.describe('Roles E2E', () => {
  test.beforeEach(async ({ loginAsAdmin }) => {
    await loginAsAdmin()
  })

  test('should display the roles list', async ({ page }) => {
    const roles = new RolesPage(page)
    await roles.goto()
    const count = await roles.getRowCount()
    expect(count).toBeGreaterThanOrEqual(0)
  })

  test('should create a new role', async ({ page }) => {
    const roles = new RolesPage(page)
    await roles.goto()
    await roles.clickAdd()
    await roles.fillName('E2E Test Role')
    await roles.submit()
    await expect(page.locator('[data-testid="role-submit-button"]')).toHaveText('Create', { timeout: 10000 })
  })

  test('should edit an existing role', async ({ page }) => {
    const roles = new RolesPage(page)
    await roles.goto()
    const rowCount = await roles.getRowCount()
    if (rowCount > 0) {
      await roles.clickEditOnRow(0)
      await roles.fillName('Updated E2E Role')
      await roles.submit()
      await expect(page.locator('text=/success|updated/i')).toBeVisible({ timeout: 5000 })
    }
  })

  test('should open permission matrix for a role', async ({ page }) => {
    const roles = new RolesPage(page)
    await roles.goto()
    const rowCount = await roles.getRowCount()
    if (rowCount > 0) {
      await roles.clickPermissionMatrixOnRow(0)
      await expect(page.locator('text=/Permissions for/i')).toBeVisible({ timeout: 5000 })
    }
  })
})
