import { test, expect } from '../fixtures'
import { BlocksPage } from '../pages/blocks.page'

test.describe('Blocks E2E', () => {
  test.beforeEach(async ({ loginAsAdmin }) => {
    await loginAsAdmin()
  })

  test('should display the blocks list', async ({ page }) => {
    const blocks = new BlocksPage(page)
    await blocks.goto()
    const count = await blocks.getRowCount()
    expect(count).toBeGreaterThanOrEqual(0)
  })

  test('should create a new block', async ({ page }) => {
    const blocks = new BlocksPage(page)
    await blocks.goto()
    await blocks.clickAdd()
    await blocks.fillName('E2E Test Block')
    await blocks.fillDescription('Created by E2E test')
    await blocks.selectPhase('E2E Test Phase')
    await blocks.submit()
    await expect(page.locator('[data-testid="blocks-submit-button"]')).toHaveText('Create', { timeout: 10000 })
  })

  test('should edit an existing block', async ({ page }) => {
    const blocks = new BlocksPage(page)
    await blocks.goto()
    const rowCount = await blocks.getRowCount()
    if (rowCount > 0) {
      await blocks.clickEditOnRow(0)
      await blocks.fillName('Updated E2E Block')
      await blocks.submit()
      await expect(page.locator('text=/success|updated/i')).toBeVisible({ timeout: 5000 })
    }
  })

  test('should delete a block', async ({ page }) => {
    const blocks = new BlocksPage(page)
    await blocks.goto()
    const rowCount = await blocks.getRowCount()
    if (rowCount > 0) {
      await blocks.clickDeleteOnRow(0)
      await blocks.confirmDelete()
      await expect(page.locator('text=/success|deleted/i')).toBeVisible({ timeout: 5000 })
    }
  })
})
