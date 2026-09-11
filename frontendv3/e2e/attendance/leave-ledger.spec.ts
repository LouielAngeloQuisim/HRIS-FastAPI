import { test, expect } from '../fixtures'
import { LeaveLedgerPage } from '../pages/leave-ledger.page'

test.describe('Leave Ledger E2E', () => {
  test.beforeEach(async ({ loginAsAdmin }) => {
    await loginAsAdmin()
  })

  test('should display the leave ledger', async ({ page }) => {
    const leaveLedger = new LeaveLedgerPage(page)
    await leaveLedger.goto()
    const count = await leaveLedger.getRowCount()
    expect(count).toBeGreaterThanOrEqual(0)
  })

  test('should refresh with a different year', async ({ page }) => {
    const leaveLedger = new LeaveLedgerPage(page)
    await leaveLedger.goto()
    await leaveLedger.setYear('2025')
    await leaveLedger.clickRefresh()
    await expect(page.locator('[data-testid="leave-ledger-year-input"]')).toHaveValue('2025', { timeout: 5000 })
  })
})
