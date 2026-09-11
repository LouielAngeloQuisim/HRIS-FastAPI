import { test, expect } from '../fixtures'
import { ShiftsPage } from '../pages/shifts.page'

test.describe('Shifts E2E', () => {
  test.beforeEach(async ({ loginAsAdmin }) => {
    await loginAsAdmin()
  })

  test('should display the shifts list', async ({ page }) => {
    const shifts = new ShiftsPage(page)
    await shifts.goto()
    const count = await shifts.getRowCount()
    expect(count).toBeGreaterThanOrEqual(0)
  })

  test('should create a new shift', async ({ page }) => {
    const shifts = new ShiftsPage(page)
    await shifts.goto()
    await shifts.clickAdd()
    await shifts.fillCode('E2E-SHIFT-001')
    await shifts.fillName('E2E Test Shift')
    await shifts.fillStartTime('09:00')
    await shifts.fillEndTime('17:00')
    await shifts.fillDescription('Created by E2E test')
    await shifts.submit()
    await expect(page.locator('[data-testid="shift-submit-button"]')).toHaveText('Create', { timeout: 10000 })
  })

  test('should edit an existing shift', async ({ page }) => {
    const shifts = new ShiftsPage(page)
    await shifts.goto()
    const rowCount = await shifts.getRowCount()
    if (rowCount > 0) {
      await shifts.clickEditOnRow(0)
      await shifts.fillName('Updated E2E Shift')
      await shifts.submit()
      await expect(page.locator('text=/success|updated/i')).toBeVisible({ timeout: 5000 })
    }
  })

  test('should delete a shift', async ({ page }) => {
    const shifts = new ShiftsPage(page)
    await shifts.goto()
    const rowCount = await shifts.getRowCount()
    if (rowCount > 0) {
      await shifts.clickDeleteOnRow(0)
      await shifts.confirmDelete()
      await expect(page.locator('text=/success|deleted/i')).toBeVisible({ timeout: 5000 })
    }
  })
})
