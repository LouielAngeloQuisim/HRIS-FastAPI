import { type Page, type Locator, expect } from '@playwright/test'

export class LotsPage {
  readonly page: Page
  readonly addButton: Locator
  readonly table: Locator
  readonly rows: Locator
  readonly lotNumberInput: Locator
  readonly descriptionInput: Locator
  readonly blockSelect: Locator
  readonly submitButton: Locator
  readonly cancelButton: Locator

  constructor(page: Page) {
    this.page = page
    this.addButton = page.locator('[data-testid="add-lots-button"]')
    this.table = page.locator('table, [role="table"]')
    this.rows = page.locator('table tbody tr, [role="row"]')
    this.lotNumberInput = page.locator('[data-testid="lots-lot-number-input"]')
    this.descriptionInput = page.locator('[data-testid="lots-description-input"]')
    this.blockSelect = page.locator('[data-testid="lots-block-select"]')
    this.submitButton = page.locator('[data-testid="lots-submit-button"]')
    this.cancelButton = page.locator('[data-testid="cancel-delete-button"]')
  }

  async goto() {
    await this.page.goto('/lots')
    await expect(this.table).toBeVisible({ timeout: 5000 })
  }

  async clickAdd() {
    await this.addButton.click()
  }

  async fillLotNumber(lotNumber: string) {
    await this.lotNumberInput.fill(lotNumber)
  }

  async fillDescription(description: string) {
    await this.descriptionInput.fill(description)
  }

  async selectBlock(label: string) {
    await this.blockSelect.click()
    await this.page.locator(`[role="option"]:has-text("${label}")`).click()
  }

  async submit() {
    await this.submitButton.click()
  }

  async clickEditOnRow(index = 0) {
    const row = this.rows.nth(index)
    const editBtn = row.locator('[data-testid^="edit-lots-button"]')
    await editBtn.click()
  }

  async clickDeleteOnRow(index = 0) {
    const row = this.rows.nth(index)
    const deleteBtn = row.locator('[data-testid^="delete-lots-button"]')
    await deleteBtn.click()
  }

  async confirmDelete() {
    await this.page.locator('[data-testid="confirm-delete-button"]').click()
  }

  async getRowCount() {
    return await this.rows.count()
  }
}
