import { type Page, type Locator, expect } from '@playwright/test'

export class PhasesPage {
  readonly page: Page
  readonly addButton: Locator
  readonly table: Locator
  readonly rows: Locator
  readonly codeInput: Locator
  readonly nameInput: Locator
  readonly descriptionInput: Locator
  readonly subdivisionSelect: Locator
  readonly submitButton: Locator
  readonly cancelButton: Locator

  constructor(page: Page) {
    this.page = page
    this.addButton = page.locator('[data-testid="add-phase-button"]')
    this.table = page.locator('table, [role="table"]')
    this.rows = page.locator('table tbody tr, [role="row"]')
    this.codeInput = page.locator('[data-testid="phase-code-input"]')
    this.nameInput = page.locator('[data-testid="phase-name-input"]')
    this.descriptionInput = page.locator('[data-testid="phase-description-input"]')
    this.subdivisionSelect = page.locator('[data-testid="phase-subdivision-select"]')
    this.submitButton = page.locator('[data-testid="phase-submit-button"]')
    this.cancelButton = page.locator('[data-testid="cancel-delete-button"]')
  }

  async goto() {
    await this.page.goto('/phases')
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

  async fillDescription(description: string) {
    await this.descriptionInput.fill(description)
  }

  async selectSubdivision(label: string) {
    await this.subdivisionSelect.click()
    await this.page.locator(`[role="option"]:has-text("${label}")`).click()
  }

  async submit() {
    await this.submitButton.click()
  }

  async clickEditOnRow(index = 0) {
    const row = this.rows.nth(index)
    const editBtn = row.locator('[data-testid^="edit-phase-button"]')
    await editBtn.click()
  }

  async clickDeleteOnRow(index = 0) {
    const row = this.rows.nth(index)
    const deleteBtn = row.locator('[data-testid^="delete-phase-button"]')
    await deleteBtn.click()
  }

  async confirmDelete() {
    await this.page.locator('[data-testid="confirm-delete-button"]').click()
  }

  async getRowCount() {
    return await this.rows.count()
  }
}
