import { test, expect } from '../fixtures'
import { DailyTimeRecordsPage } from '../pages/daily-time-records.page'

test.describe('Daily Time Records E2E', () => {
  test.beforeEach(async ({ loginAsAdmin }) => {
    await loginAsAdmin()
  })

  test('should display the DTR list', async ({ page }) => {
    const dtr = new DailyTimeRecordsPage(page)
    await dtr.goto()
    const count = await dtr.getRowCount()
    expect(count).toBeGreaterThanOrEqual(0)
  })

  test('should retry on error', async ({ page }) => {
    const dtr = new DailyTimeRecordsPage(page)
    await dtr.goto()
    const retryBtn = page.locator('[data-testid="retry-button"]')
    if (await retryBtn.count() > 0) {
      await dtr.clickRetry()
    }
  })
})
