import { type Page, type Locator, expect } from '@playwright/test'

export class DtrAdjustmentsPage {
  readonly page: Page
  readonly table: Locator
  readonly rows: Locator
  readonly newButton: Locator
  readonly retryButton: Locator
  readonly dtrIdInput: Locator
  readonly loginInput: Locator
  readonly logoutInput: Locator
  readonly reasonInput: Locator
  readonly submitButton: Locator

  constructor(page: Page) {
    this.page = page
    this.table = page.locator('table, [role="table"]')
    this.rows = page.locator('table tbody tr, [role="row"]')
    this.newButton = page.locator('[data-testid="new-dtr-adjustment-button"]')
    this.retryButton = page.locator('[data-testid="retry-button"]')
    this.dtrIdInput = page.locator('[data-testid="dtr-adjustment-dtr-id-input"]')
    this.loginInput = page.locator('[data-testid="dtr-adjustment-login-input"]')
    this.logoutInput = page.locator('[data-testid="dtr-adjustment-logout-input"]')
    this.reasonInput = page.locator('[data-testid="dtr-adjustment-reason-input"]')
    this.submitButton = page.locator('[data-testid="dtr-adjustment-submit-button"]')
  }

  async goto() {
    await this.page.goto('/dtr-adjustments')
    await expect(this.table).toBeVisible({ timeout: 5000 })
  }

  async clickNew() {
    await this.newButton.click()
  }

  async fillDtrId(id: string) {
    await this.dtrIdInput.fill(id)
  }

  async fillAdjustedLogin(date: string) {
    await this.loginInput.fill(date)
  }

  async fillAdjustedLogout(date: string) {
    await this.logoutInput.fill(date)
  }

  async fillReason(reason: string) {
    await this.reasonInput.fill(reason)
  }

  async submit() {
    await this.submitButton.click()
  }

  async approveOnRow(id: string) {
    const btn = this.page.locator(`[data-testid="approve-dtr-adjustment-button-${id}"]`)
    await btn.click()
  }

  async rejectOnRow(id: string) {
    const btn = this.page.locator(`[data-testid="reject-dtr-adjustment-button-${id}"]`)
    await btn.click()
  }

  async getRowCount() {
    return await this.rows.count()
  }
}
