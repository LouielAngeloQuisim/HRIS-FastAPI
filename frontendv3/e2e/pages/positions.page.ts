import { type Page, type Locator, expect } from '@playwright/test'

export class PositionsPage {
  readonly page: Page
  readonly addButton: Locator
  readonly table: Locator
  readonly rows: Locator
  readonly codeInput: Locator
  readonly titleInput: Locator
  readonly descriptionInput: Locator
  readonly departmentSelect: Locator
  readonly submitButton: Locator
  readonly cancelButton: Locator

  constructor(page: Page) {
    this.page = page
    this.addButton = page.locator('[data-testid="add-position-button"]')
    this.table = page.locator('table, [role="table"]')
    this.rows = page.locator('table tbody tr, [role="row"]')
    this.codeInput = page.locator('[data-testid="position-code-input"]')
    this.titleInput = page.locator('[data-testid="position-title-input"]')
    this.descriptionInput = page.locator('[data-testid="position-description-input"]')
    this.departmentSelect = page.locator('[data-testid="position-department-select"]')
    this.submitButton = page.locator('[data-testid="position-submit-button"]')
    this.cancelButton = page.locator('[data-testid="cancel-delete-button"]')
  }

  async goto() {
    await this.page.goto('/positions')
    await expect(this.table).toBeVisible({ timeout: 5000 })
  }

  async clickAdd() {
    await this.addButton.click()
  }

  async fillCode(code: string) {
    await this.codeInput.fill(code)
  }

  async fillTitle(title: string) {
    await this.titleInput.fill(title)
  }

  async fillDescription(description: string) {
    await this.descriptionInput.fill(description)
  }

  async selectDepartment(label: string) {
    await this.departmentSelect.click()
    await this.page.locator(`[role="option"]:has-text("${label}")`).click()
  }

  async submit() {
    await this.submitButton.click()
  }

  async clickEditOnRow(index = 0) {
    const row = this.rows.nth(index)
    const editBtn = row.locator('[data-testid^="edit-position-button"]')
    await editBtn.click()
  }

  async clickDeleteOnRow(index = 0) {
    const row = this.rows.nth(index)
    const deleteBtn = row.locator('[data-testid^="delete-position-button"]')
    await deleteBtn.click()
  }

  async confirmDelete() {
    await this.page.locator('[data-testid="confirm-delete-button"]').click()
  }

  async getRowCount() {
    return await this.rows.count()
  }
}
