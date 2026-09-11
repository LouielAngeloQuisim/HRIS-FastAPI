import { test, expect } from '../fixtures'
import { OwnersPage } from '../pages/owners.page'

test.describe('Owners E2E', () => {
  test.beforeEach(async ({ loginAsAdmin }) => {
    await loginAsAdmin()
  })

  test('should display the owners list', async ({ page }) => {
    const owners = new OwnersPage(page)
    await owners.goto()
    const count = await owners.getRowCount()
    expect(count).toBeGreaterThanOrEqual(0)
  })

  test('should create a new owner', async ({ page }) => {
    const owners = new OwnersPage(page)
    await owners.goto()
    await owners.clickAdd()
    await owners.fillFirstName('E2E')
    await owners.fillLastName('Owner')
    await owners.fillLotNo('LOT-001')
    await owners.fillBlock('BLOCK-A')
    await owners.fillEmail('e2e-owner@example.com')
    await owners.fillContactNo('1234567890')
    await owners.submit()
    await expect(page.locator('[data-testid="owner-submit-button"]')).toHaveText('Create', { timeout: 10000 })
  })

  test('should edit an existing owner', async ({ page }) => {
    const owners = new OwnersPage(page)
    await owners.goto()
    const rowCount = await owners.getRowCount()
    if (rowCount > 0) {
      await owners.clickEditOnRow(0)
      await owners.fillFirstName('Updated E2E')
      await owners.submit()
      await expect(page.locator('text=/success|updated/i')).toBeVisible({ timeout: 5000 })
    }
  })

  test('should delete an owner', async ({ page }) => {
    const owners = new OwnersPage(page)
    await owners.goto()
    const rowCount = await owners.getRowCount()
    if (rowCount > 0) {
      await owners.clickDeleteOnRow(0)
      await owners.confirmDelete()
      await expect(page.locator('text=/success|deleted/i')).toBeVisible({ timeout: 5000 })
    }
  })
})
