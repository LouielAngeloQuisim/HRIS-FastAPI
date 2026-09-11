import { type Page, type Locator, expect } from '@playwright/test'

export class LeaveCalendarPage {
  readonly page: Page
  readonly table: Locator
  readonly rows: Locator
  readonly fromDateInput: Locator
  readonly toDateInput: Locator
  readonly applyButton: Locator

  constructor(page: Page) {
    this.page = page
    this.table = page.locator('table, [role="table"]')
    this.rows = page.locator('table tbody tr, [role="row"]')
    this.fromDateInput = page.locator('[data-testid="leave-calendar-from-date"]')
    this.toDateInput = page.locator('[data-testid="leave-calendar-to-date"]')
    this.applyButton = page.locator('[data-testid="leave-calendar-apply-button"]')
  }

  async goto() {
    await this.page.goto('/leave-calendar')
    await expect(this.table).toBeVisible({ timeout: 5000 })
  }

  async setFromDate(date: string) {
    await this.fromDateInput.fill(date)
  }

  async setToDate(date: string) {
    await this.toDateInput.fill(date)
  }

  async clickApply() {
    await this.applyButton.click()
  }

  async getRowCount() {
    return await this.rows.count()
  }
}
