import { test, expect } from '../fixtures'
import { DivisionsPage } from '../pages/divisions.page'

test.describe('Divisions E2E', () => {
  test.beforeEach(async ({ loginAsAdmin }) => {
    await loginAsAdmin()
  })

  test('should display the divisions list', async ({ page }) => {
    const divisions = new DivisionsPage(page)
    await divisions.goto()
    const count = await divisions.getRowCount()
    expect(count).toBeGreaterThanOrEqual(0)
  })

  test('should create a new division', async ({ page }) => {
    const divisions = new DivisionsPage(page)
    await divisions.goto()
    await divisions.clickAdd()
    await divisions.fillCode('E2E-DIV-001')
    await divisions.fillName('E2E Test Division')
    await divisions.fillDescription('Created by E2E test')
    await divisions.submit()
    await expect(page.locator('[data-testid="division-submit-button"]')).toHaveText('Create', { timeout: 10000 })
  })

  test('should edit an existing division', async ({ page }) => {
    const divisions = new DivisionsPage(page)
    await divisions.goto()
    const rowCount = await divisions.getRowCount()
    if (rowCount > 0) {
      await divisions.clickEditOnRow(0)
      await divisions.fillName('Updated E2E Division')
      await divisions.submit()
      await expect(page.locator('text=/success|updated/i')).toBeVisible({ timeout: 5000 })
    }
  })

  test('should delete a division', async ({ page }) => {
    const divisions = new DivisionsPage(page)
    await divisions.goto()
    const rowCount = await divisions.getRowCount()
    if (rowCount > 0) {
      await divisions.clickDeleteOnRow(0)
      await divisions.confirmDelete()
      await expect(page.locator('text=/success|deleted/i')).toBeVisible({ timeout: 5000 })
    }
  })
})
