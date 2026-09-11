import { type Page, type Locator, expect } from '@playwright/test'

export class DepartmentsPage {
  readonly page: Page
  readonly addButton: Locator
  readonly table: Locator
  readonly rows: Locator
  readonly nameInput: Locator
  readonly codeInput: Locator
  readonly descriptionInput: Locator
  readonly divisionSelect: Locator
  readonly submitButton: Locator
  readonly cancelButton: Locator

  constructor(page: Page) {
    this.page = page
    this.addButton = page.locator('[data-testid="add-department-button"]')
    this.table = page.locator('table, [role="table"]')
    this.rows = page.locator('table tbody tr, [role="row"]')
    this.nameInput = page.locator('[data-testid="department-name-input"]')
    this.codeInput = page.locator('[data-testid="department-code-input"]')
    this.descriptionInput = page.locator('[data-testid="department-description-input"]')
    this.divisionSelect = page.locator('[data-testid="department-division-select"]')
    this.submitButton = page.locator('[data-testid="department-submit-button"]')
    this.cancelButton = page.locator('[data-testid="cancel-delete-button"]')
  }

  async goto() {
    await this.page.goto('/departments')
    await expect(this.table).toBeVisible({ timeout: 5000 })
  }

  async clickAdd() {
    await this.addButton.click()
  }

  async fillName(name: string) {
    await this.nameInput.fill(name)
  }

  async fillCode(code: string) {
    await this.codeInput.fill(code)
  }

  async fillDescription(description: string) {
    await this.descriptionInput.fill(description)
  }

  async selectDivision(label: string) {
    await this.divisionSelect.click()
    await this.page.locator(`[role="option"]:has-text("${label}")`).click()
  }

  async submit() {
    await this.submitButton.click()
  }

  async clickEditOnRow(index = 0) {
    const row = this.rows.nth(index)
    const editBtn = row.locator('[data-testid^="edit-department-button"]')
    await editBtn.click()
  }

  async clickDeleteOnRow(index = 0) {
    const row = this.rows.nth(index)
    const deleteBtn = row.locator('[data-testid^="delete-department-button"]')
    await deleteBtn.click()
  }

  async confirmDelete() {
    await this.page.locator('[data-testid="confirm-delete-button"]').click()
  }

  async getRowCount() {
    return await this.rows.count()
  }
}
