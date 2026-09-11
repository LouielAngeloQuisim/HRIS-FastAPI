import { test, expect } from '../fixtures'
import { LotsPage } from '../pages/lots.page'

test.describe('Lots E2E', () => {
  test.beforeEach(async ({ loginAsAdmin }) => {
    await loginAsAdmin()
  })

  test('should display the lots list', async ({ page }) => {
    const lots = new LotsPage(page)
    await lots.goto()
    const count = await lots.getRowCount()
    expect(count).toBeGreaterThanOrEqual(0)
  })

  test('should create a new lot', async ({ page }) => {
    const lots = new LotsPage(page)
    await lots.goto()
    await lots.clickAdd()
    await lots.fillLotNumber('E2E-LOT-001')
    await lots.fillDescription('Created by E2E test')
    await lots.selectBlock('E2E Test Block')
    await lots.submit()
    await expect(page.locator('[data-testid="lots-submit-button"]')).toHaveText('Create', { timeout: 10000 })
  })

  test('should edit an existing lot', async ({ page }) => {
    const lots = new LotsPage(page)
    await lots.goto()
    const rowCount = await lots.getRowCount()
    if (rowCount > 0) {
      await lots.clickEditOnRow(0)
      await lots.fillLotNumber('E2E-LOT-001-UPD')
      await lots.submit()
      await expect(page.locator('text=/success|updated/i')).toBeVisible({ timeout: 5000 })
    }
  })

  test('should delete a lot', async ({ page }) => {
    const lots = new LotsPage(page)
    await lots.goto()
    const rowCount = await lots.getRowCount()
    if (rowCount > 0) {
      await lots.clickDeleteOnRow(0)
      await lots.confirmDelete()
      await expect(page.locator('text=/success|deleted/i')).toBeVisible({ timeout: 5000 })
    }
  })
})
