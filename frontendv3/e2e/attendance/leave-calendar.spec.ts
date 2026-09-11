import { test, expect } from '../fixtures'
import { LeaveCalendarPage } from '../pages/leave-calendar.page'

test.describe('Leave Calendar E2E', () => {
  test.beforeEach(async ({ loginAsAdmin }) => {
    await loginAsAdmin()
  })

  test('should display the leave calendar', async ({ page }) => {
    const leaveCalendar = new LeaveCalendarPage(page)
    await leaveCalendar.goto()
    const count = await leaveCalendar.getRowCount()
    expect(count).toBeGreaterThanOrEqual(0)
  })

  test('should apply date range filter', async ({ page }) => {
    const leaveCalendar = new LeaveCalendarPage(page)
    await leaveCalendar.goto()
    await leaveCalendar.setFromDate('2026-01-01')
    await leaveCalendar.setToDate('2026-12-31')
    await leaveCalendar.clickApply()
    await expect(page.locator('[data-testid="leave-calendar-from-date"]')).toHaveValue('2026-01-01', { timeout: 5000 })
  })
})
