import { type Page, type Locator, expect } from '@playwright/test'

export class LeaveRequestsPage {
  readonly page: Page
  readonly table: Locator
  readonly rows: Locator
  readonly newButton: Locator
  readonly statusFilter: Locator
  readonly retryButton: Locator
  readonly employeeIdInput: Locator
  readonly policyIdInput: Locator
  readonly dateStartInput: Locator
  readonly dateEndInput: Locator
  readonly reasonInput: Locator
  readonly submitButton: Locator

  constructor(page: Page) {
    this.page = page
    this.table = page.locator('table, [role="table"]')
    this.rows = page.locator('table tbody tr, [role="row"]')
    this.newButton = page.locator('[data-testid="new-leave-request-button"]')
    this.statusFilter = page.locator('[data-testid="leave-request-status-filter"]')
    this.retryButton = page.locator('[data-testid="retry-button"]')
    this.employeeIdInput = page.locator('[data-testid="leave-request-employee-id-input"]')
    this.policyIdInput = page.locator('[data-testid="leave-request-policy-id-input"]')
    this.dateStartInput = page.locator('[data-testid="leave-request-date-start-input"]')
    this.dateEndInput = page.locator('[data-testid="leave-request-date-end-input"]')
    this.reasonInput = page.locator('[data-testid="leave-request-reason-input"]')
    this.submitButton = page.locator('[data-testid="leave-request-submit-button"]')
  }

  async goto() {
    await this.page.goto('/leave-requests')
    await expect(this.table).toBeVisible({ timeout: 5000 })
  }

  async clickNew() {
    await this.newButton.click()
  }

  async fillEmployeeId(id: string) {
    await this.employeeIdInput.fill(id)
  }

  async fillPolicyId(id: string) {
    await this.policyIdInput.fill(id)
  }

  async fillDateStart(date: string) {
    await this.dateStartInput.fill(date)
  }

  async fillDateEnd(date: string) {
    await this.dateEndInput.fill(date)
  }

  async fillReason(reason: string) {
    await this.reasonInput.fill(reason)
  }

  async submit() {
    await this.submitButton.click()
  }

  async approveOnRow(id: string) {
    const btn = this.page.locator(`[data-testid="approve-leave-request-button-${id}"]`)
    await btn.click()
  }

  async rejectOnRow(id: string) {
    const btn = this.page.locator(`[data-testid="reject-leave-request-button-${id}"]`)
    await btn.click()
  }

  async getRowCount() {
    return await this.rows.count()
  }
}
