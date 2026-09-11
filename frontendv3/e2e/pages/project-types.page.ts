import { type Page, type Locator, expect } from '@playwright/test'

export class ProjectTypesPage {
  readonly page: Page
  readonly addButton: Locator
  readonly table: Locator
  readonly rows: Locator
  readonly codeInput: Locator
  readonly nameInput: Locator
  readonly descriptionInput: Locator
  readonly submitButton: Locator
  readonly cancelButton: Locator

  constructor(page: Page) {
    this.page = page
    this.addButton = page.locator('[data-testid="add-project-type-button"]')
    this.table = page.locator('table, [role="table"]')
    this.rows = page.locator('table tbody tr, [role="row"]')
    this.codeInput = page.locator('[data-testid="project-type-code-input"]')
    this.nameInput = page.locator('[data-testid="project-type-name-input"]')
    this.descriptionInput = page.locator('[data-testid="project-type-description-input"]')
    this.submitButton = page.locator('[data-testid="project-type-submit-button"]')
    this.cancelButton = page.locator('[data-testid="cancel-delete-button"]')
  }

  async goto() {
    await this.page.goto('/project-types')
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

  async submit() {
    await this.submitButton.click()
  }

  async clickEditOnRow(index = 0) {
    const row = this.rows.nth(index)
    const editBtn = row.locator('[data-testid^="edit-project-type-button"]')
    await editBtn.click()
  }

  async clickDeleteOnRow(index = 0) {
    const row = this.rows.nth(index)
    const deleteBtn = row.locator('[data-testid^="delete-project-type-button"]')
    await deleteBtn.click()
  }

  async confirmDelete() {
    await this.page.locator('[data-testid="confirm-delete-button"]').click()
  }

  async getRowCount() {
    return await this.rows.count()
  }
}
