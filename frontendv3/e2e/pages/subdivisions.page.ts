import { type Page, type Locator, expect } from '@playwright/test'

export class SubdivisionsPage {
  readonly page: Page
  readonly addButton: Locator
  readonly wizardButton: Locator
  readonly table: Locator
  readonly rows: Locator
  readonly codeInput: Locator
  readonly nameInput: Locator
  readonly descriptionInput: Locator
  readonly locationInput: Locator
  readonly departmentSelect: Locator
  readonly submitButton: Locator
  readonly cancelButton: Locator

  constructor(page: Page) {
    this.page = page
    this.addButton = page.locator('[data-testid="add-subdivision-button"]')
    this.wizardButton = page.locator('[data-testid="subdivision-wizard-button"]')
    this.table = page.locator('table, [role="table"]')
    this.rows = page.locator('table tbody tr, [role="row"]')
    this.codeInput = page.locator('[data-testid="subdivision-code-input"]')
    this.nameInput = page.locator('[data-testid="subdivision-name-input"]')
    this.descriptionInput = page.locator('[data-testid="subdivision-description-input"]')
    this.locationInput = page.locator('[data-testid="subdivision-location-input"]')
    this.departmentSelect = page.locator('[data-testid="subdivision-department-select"]')
    this.submitButton = page.locator('[data-testid="subdivision-submit-button"]')
    this.cancelButton = page.locator('[data-testid="cancel-delete-button"]')
  }

  async goto() {
    await this.page.goto('/subdivisions')
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

  async fillLocation(location: string) {
    await this.locationInput.fill(location)
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
    const editBtn = row.locator('[data-testid^="edit-subdivision-button"]')
    await editBtn.click()
  }

  async clickDeleteOnRow(index = 0) {
    const row = this.rows.nth(index)
    const deleteBtn = row.locator('[data-testid^="delete-subdivision-button"]')
    await deleteBtn.click()
  }

  async confirmDelete() {
    await this.page.locator('[data-testid="confirm-delete-button"]').click()
  }

  async getRowCount() {
    return await this.rows.count()
  }
}
