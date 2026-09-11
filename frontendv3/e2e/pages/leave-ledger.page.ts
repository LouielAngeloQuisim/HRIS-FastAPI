import { type Page, type Locator, expect } from '@playwright/test'

export class LeaveLedgerPage {
  readonly page: Page
  readonly table: Locator
  readonly rows: Locator
  readonly yearInput: Locator
  readonly refreshButton: Locator

  constructor(page: Page) {
    this.page = page
    this.table = page.locator('table, [role="table"]')
    this.rows = page.locator('table tbody tr, [role="row"]')
    this.yearInput = page.locator('[data-testid="leave-ledger-year-input"]')
    this.refreshButton = page.locator('[data-testid="leave-ledger-refresh-button"]')
  }

  async goto() {
    await this.page.goto('/leave-ledger')
    await expect(this.table).toBeVisible({ timeout: 5000 })
  }

  async setYear(year: string) {
    await this.yearInput.fill(year)
  }

  async clickRefresh() {
    await this.refreshButton.click()
  }

  async getRowCount() {
    return await this.rows.count()
  }
}
