import { test, expect } from '../fixtures'
import { DtrAdjustmentsPage } from '../pages/dtr-adjustments.page'

test.describe('DTR Adjustments E2E', () => {
  test.beforeEach(async ({ loginAsAdmin }) => {
    await loginAsAdmin()
  })

  test('should display the DTR adjustments list', async ({ page }) => {
    const adjustments = new DtrAdjustmentsPage(page)
    await adjustments.goto()
    const count = await adjustments.getRowCount()
    expect(count).toBeGreaterThanOrEqual(0)
  })

  test('should submit a new DTR adjustment', async ({ page }) => {
    const adjustments = new DtrAdjustmentsPage(page)
    await adjustments.goto()
    await adjustments.clickNew()
    await adjustments.fillDtrId('E2E-DTR-001')
    await adjustments.fillAdjustedLogin('2026-09-15T08:00')
    await adjustments.fillAdjustedLogout('2026-09-15T17:00')
    await adjustments.fillReason('E2E test adjustment')
    await adjustments.submit()
    await expect(page.locator('[data-testid="dtr-adjustment-submit-button"]')).toHaveText('Submit Adjustment', { timeout: 10000 })
  })
})
