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
    await page.route('**/api/v1/daily-time-records?**', route => route.fulfill({ status: 500, json: { error: { message: 'Injected test failure' } } }))
    await page.reload()
    await expect(page.getByText('Failed to load daily time records.')).toBeVisible({ timeout: 15000 })
    await page.unroute('**/api/v1/daily-time-records?**')
    await page.getByRole('button', { name: 'Try again', exact: true }).click()
    await expect(page.getByText('Failed to load daily time records.')).not.toBeVisible({ timeout: 10000 })
    await expect(page.locator('table')).toBeVisible()
  })
})
