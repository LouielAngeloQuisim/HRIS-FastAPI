import { type Page, type Locator, expect } from '@playwright/test'

export class ProjectsPage {
  readonly page: Page
  readonly addButton: Locator
  readonly table: Locator
  readonly rows: Locator
  readonly codeInput: Locator
  readonly nameInput: Locator
  readonly descriptionInput: Locator
  readonly subdivisionSelect: Locator
  readonly projectTypeSelect: Locator
  readonly submitButton: Locator
  readonly cancelButton: Locator

  constructor(page: Page) {
    this.page = page
    this.addButton = page.locator('[data-testid="add-project-button"]')
    this.table = page.locator('table, [role="table"]')
    this.rows = page.locator('table tbody tr, [role="row"]')
    this.codeInput = page.locator('[data-testid="project-code-input"]')
    this.nameInput = page.locator('[data-testid="project-name-input"]')
    this.descriptionInput = page.locator('[data-testid="project-description-input"]')
    this.subdivisionSelect = page.locator('[data-testid="project-subdivision-select"]')
    this.projectTypeSelect = page.locator('[data-testid="project-type-select"]')
    this.submitButton = page.locator('[data-testid="project-submit-button"]')
    this.cancelButton = page.locator('[data-testid="cancel-delete-button"]')
  }

  async goto() {
    await this.page.goto('/projects')
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

  async selectProjectType(label: string) {
    await this.projectTypeSelect.click()
    await this.page.locator(`[role="option"]:has-text("${label}")`).click()
  }

  async submit() {
    await this.submitButton.click()
  }

  async clickEditOnRow(index = 0) {
    const row = this.rows.nth(index)
    const editBtn = row.locator('[data-testid^="edit-project-button"]')
    await editBtn.click()
  }

  async clickDeleteOnRow(index = 0) {
    const row = this.rows.nth(index)
    const deleteBtn = row.locator('[data-testid^="delete-project-button"]')
    await deleteBtn.click()
  }

  async confirmDelete() {
    await this.page.locator('[data-testid="confirm-delete-button"]').click()
  }

  async getRowCount() {
    return await this.rows.count()
  }
}
