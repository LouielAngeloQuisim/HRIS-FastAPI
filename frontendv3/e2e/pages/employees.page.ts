import { type Page, type Locator, expect } from '@playwright/test'

export class EmployeesPage {
  readonly page: Page
  readonly table: Locator
  readonly rows: Locator
  readonly csvImportButton: Locator
  readonly retryButton: Locator

  constructor(page: Page) {
    this.page = page
    this.table = page.locator('table, [role="table"]')
    this.rows = page.locator('table tbody tr, [role="row"]')
    this.csvImportButton = page.locator('[data-testid="employee-csv-import-button"]')
    this.retryButton = page.locator('[data-testid="retry-button"]')
  }

  async goto() {
    await this.page.goto('/employees')
    await expect(this.table).toBeVisible({ timeout: 5000 })
  }

  async clickCsvImport() {
    await this.csvImportButton.click()
  }

  async clickRetry() {
    await this.retryButton.click()
  }

  async getRowCount() {
    return await this.rows.count()
  }
}
