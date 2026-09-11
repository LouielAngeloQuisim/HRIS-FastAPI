import { type Page, type Locator, expect } from '@playwright/test'

export class DailyTimeRecordsPage {
  readonly page: Page
  readonly table: Locator
  readonly rows: Locator
  readonly retryButton: Locator

  constructor(page: Page) {
    this.page = page
    this.table = page.locator('table, [role="table"]')
    this.rows = page.locator('table tbody tr, [role="row"]')
    this.retryButton = page.locator('[data-testid="retry-button"]')
  }

  async goto() {
    await this.page.goto('/daily-time-records')
    await expect(this.table).toBeVisible({ timeout: 5000 })
  }

  async clickRetry() {
    await this.retryButton.click()
  }

  async approveOvertimeOnRow(id: string) {
    const btn = this.page.locator(`[data-testid="approve-overtime-button-${id}"]`)
    await btn.click()
  }

  async rejectOvertimeOnRow(id: string) {
    const btn = this.page.locator(`[data-testid="reject-overtime-button-${id}"]`)
    await btn.click()
  }

  async getRowCount() {
    return await this.rows.count()
  }
}
