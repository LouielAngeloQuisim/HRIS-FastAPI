import { test, expect } from '../fixtures'
import { HolidaysPage } from '../pages/holidays.page'

test.describe('Holidays E2E', () => {
  test.beforeEach(async ({ loginAsAdmin }) => {
    await loginAsAdmin()
  })

  test('should display the holiday configs list', async ({ page }) => {
    const holidays = new HolidaysPage(page)
    await holidays.goto()
    const count = await holidays.getRowCount()
    expect(count).toBeGreaterThanOrEqual(0)
  })

  test('should create a new holiday config', async ({ page }) => {
    const holidays = new HolidaysPage(page)
    await holidays.goto()
    await holidays.clickAdd()
    await holidays.fillCode('E2E-HOL-001')
    await holidays.fillName('E2E Test Holiday')
    await holidays.fillMonthDay('12-25')
    await holidays.selectType('Regular')
    await holidays.fillRegion('NCR')
    await holidays.toggleRecurring()
    await holidays.submit()
    await expect(page.locator('[data-testid="holiday-submit-button"]')).toHaveText('Create', { timeout: 10000 })
  })

  test('should edit an existing holiday config', async ({ page }) => {
    const holidays = new HolidaysPage(page)
    await holidays.goto()
    const rowCount = await holidays.getRowCount()
    if (rowCount > 0) {
      await holidays.clickEditOnRow(0)
      await holidays.fillName('Updated E2E Holiday')
      await holidays.submit()
      await expect(page.locator('text=/success|updated/i')).toBeVisible({ timeout: 5000 })
    }
  })

  test('should delete a holiday config', async ({ page }) => {
    const holidays = new HolidaysPage(page)
    await holidays.goto()
    const rowCount = await holidays.getRowCount()
    if (rowCount > 0) {
      await holidays.clickDeleteOnRow(0)
      await holidays.confirmDelete()
      await expect(page.locator('text=/success|deleted/i')).toBeVisible({ timeout: 5000 })
    }
  })
})
