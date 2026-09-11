import { type Page, type Locator, expect } from '@playwright/test'

export class ShiftsPage {
  readonly page: Page
  readonly addButton: Locator
  readonly table: Locator
  readonly rows: Locator
  readonly codeInput: Locator
  readonly nameInput: Locator
  readonly startTimeInput: Locator
  readonly endTimeInput: Locator
  readonly descriptionInput: Locator
  readonly submitButton: Locator
  readonly cancelButton: Locator

  constructor(page: Page) {
    this.page = page
    this.addButton = page.locator('[data-testid="add-shift-button"]')
    this.table = page.locator('table, [role="table"]')
    this.rows = page.locator('table tbody tr, [role="row"]')
    this.codeInput = page.locator('[data-testid="shift-code-input"]')
    this.nameInput = page.locator('[data-testid="shift-name-input"]')
    this.startTimeInput = page.locator('[data-testid="shift-start-time-input"]')
    this.endTimeInput = page.locator('[data-testid="shift-end-time-input"]')
    this.descriptionInput = page.locator('[data-testid="shift-description-input"]')
    this.submitButton = page.locator('[data-testid="shift-submit-button"]')
    this.cancelButton = page.locator('[data-testid="cancel-delete-button"]')
  }

  async goto() {
    await this.page.goto('/shifts')
    await expect(this.table).toBeVisible({ timeout: 5000 })
  }

  async clickAdd() {
    await this.addButton.click()
  }

  async fillCode(code: string) {
    await this.codeInput.fill(code)
  }

  async fillName(name: string) {
    await this.nameInput.fill(name)
  }

  async fillStartTime(time: string) {
    await this.startTimeInput.fill(time)
  }

  async fillEndTime(time: string) {
    await this.endTimeInput.fill(time)
  }

  async fillDescription(description: string) {
    await this.descriptionInput.fill(description)
  }

  async submit() {
    await this.submitButton.click()
  }

  async clickEditOnRow(index = 0) {
    const row = this.rows.nth(index)
    const editBtn = row.locator('[data-testid^="edit-shift-button"]')
    await editBtn.click()
  }

  async clickDeleteOnRow(index = 0) {
    const row = this.rows.nth(index)
    const deleteBtn = row.locator('[data-testid^="delete-shift-button"]')
    await deleteBtn.click()
  }

  async confirmDelete() {
    await this.page.locator('[data-testid="confirm-delete-button"]').click()
  }

  async getRowCount() {
    return await this.rows.count()
  }
}
