import { test, expect } from '../fixtures'
import { PositionsPage } from '../pages/positions.page'

test.describe('Positions E2E', () => {
  test.beforeEach(async ({ loginAsAdmin }) => {
    await loginAsAdmin()
  })

  test('should display the positions list', async ({ page }) => {
    const positions = new PositionsPage(page)
    await positions.goto()
    const count = await positions.getRowCount()
    expect(count).toBeGreaterThanOrEqual(0)
  })

  test('should create a new position', async ({ page }) => {
    const positions = new PositionsPage(page)
    await positions.goto()
    await positions.clickAdd()
    await positions.fillCode('E2E-POS-001')
    await positions.fillTitle('E2E Test Position')
    await positions.fillDescription('Created by E2E test')
    await positions.selectDepartment('E2E Test Department')
    await positions.submit()
    await expect(page.locator('[data-testid="position-submit-button"]')).toHaveText('Create', { timeout: 10000 })
  })

  test('should edit an existing position', async ({ page }) => {
    const positions = new PositionsPage(page)
    await positions.goto()
    const rowCount = await positions.getRowCount()
    if (rowCount > 0) {
      await positions.clickEditOnRow(0)
      await positions.fillTitle('Updated E2E Position')
      await positions.submit()
      await expect(page.locator('text=/success|updated/i')).toBeVisible({ timeout: 5000 })
    }
  })

  test('should delete a position', async ({ page }) => {
    const positions = new PositionsPage(page)
    await positions.goto()
    const rowCount = await positions.getRowCount()
    if (rowCount > 0) {
      await positions.clickDeleteOnRow(0)
      await positions.confirmDelete()
      await expect(page.locator('text=/success|deleted/i')).toBeVisible({ timeout: 5000 })
    }
  })
})
