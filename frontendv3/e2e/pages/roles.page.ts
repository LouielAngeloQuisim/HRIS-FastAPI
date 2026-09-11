import { type Page, type Locator, expect } from '@playwright/test'

export class RolesPage {
  readonly page: Page
  readonly addButton: Locator
  readonly table: Locator
  readonly rows: Locator
  readonly nameInput: Locator
  readonly submitButton: Locator
  readonly cancelButton: Locator
  readonly permissionMatrixButton: Locator

  constructor(page: Page) {
    this.page = page
    this.addButton = page.locator('[data-testid="add-role-button"]')
    this.table = page.locator('table, [role="table"]')
    this.rows = page.locator('table tbody tr, [role="row"]')
    this.nameInput = page.locator('[data-testid="role-name-input"]')
    this.submitButton = page.locator('[data-testid="role-submit-button"]')
    this.cancelButton = page.locator('[data-testid="cancel-delete-button"]')
    this.permissionMatrixButton = page.locator('[data-testid^="role-permission-matrix-button"]')
  }

  async goto() {
    await this.page.goto('/roles')
    await expect(this.table).toBeVisible({ timeout: 5000 })
  }

  async clickAdd() {
    await this.addButton.click()
  }

  async fillName(name: string) {
    await this.nameInput.fill(name)
  }

  async submit() {
    await this.submitButton.click()
  }

  async clickEditOnRow(index = 0) {
    const row = this.rows.nth(index)
    const editBtn = row.locator('[data-testid^="edit-role-button"]')
    await editBtn.click()
  }

  async clickPermissionMatrixOnRow(index = 0) {
    const row = this.rows.nth(index)
    const matrixBtn = row.locator('[data-testid^="role-permission-matrix-button"]')
    await matrixBtn.click()
  }

  async getRowCount() {
    return await this.rows.count()
  }
}
