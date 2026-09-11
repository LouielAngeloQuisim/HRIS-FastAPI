import { type Page, type Locator, expect } from '@playwright/test'

export class OwnersPage {
  readonly page: Page
  readonly addButton: Locator
  readonly table: Locator
  readonly rows: Locator
  readonly firstNameInput: Locator
  readonly lastNameInput: Locator
  readonly lotNoInput: Locator
  readonly blockInput: Locator
  readonly emailInput: Locator
  readonly contactNoInput: Locator
  readonly submitButton: Locator
  readonly cancelButton: Locator

  constructor(page: Page) {
    this.page = page
    this.addButton = page.locator('[data-testid="add-owner-button"]')
    this.table = page.locator('table, [role="table"]')
    this.rows = page.locator('table tbody tr, [role="row"]')
    this.firstNameInput = page.locator('[data-testid="owner-first-name-input"]')
    this.lastNameInput = page.locator('[data-testid="owner-last-name-input"]')
    this.lotNoInput = page.locator('[data-testid="owner-lot-no-input"]')
    this.blockInput = page.locator('[data-testid="owner-block-input"]')
    this.emailInput = page.locator('[data-testid="owner-email-input"]')
    this.contactNoInput = page.locator('[data-testid="owner-contact-no-input"]')
    this.submitButton = page.locator('[data-testid="owner-submit-button"]')
    this.cancelButton = page.locator('[data-testid="cancel-delete-button"]')
  }

  async goto() {
    await this.page.goto('/owners')
    await expect(this.table).toBeVisible({ timeout: 5000 })
  }

  async clickAdd() {
    await this.addButton.click()
  }

  async fillFirstName(firstName: string) {
    await this.firstNameInput.fill(firstName)
  }

  async fillLastName(lastName: string) {
    await this.lastNameInput.fill(lastName)
  }

  async fillLotNo(lotNo: string) {
    await this.lotNoInput.fill(lotNo)
  }

  async fillBlock(block: string) {
    await this.blockInput.fill(block)
  }

  async fillEmail(email: string) {
    await this.emailInput.fill(email)
  }

  async fillContactNo(contactNo: string) {
    await this.contactNoInput.fill(contactNo)
  }

  async submit() {
    await this.submitButton.click()
  }

  async clickEditOnRow(index = 0) {
    const row = this.rows.nth(index)
    const editBtn = row.locator('[data-testid^="edit-owner-button"]')
    await editBtn.click()
  }

  async clickDeleteOnRow(index = 0) {
    const row = this.rows.nth(index)
    const deleteBtn = row.locator('[data-testid^="delete-owner-button"]')
    await deleteBtn.click()
  }

  async confirmDelete() {
    await this.page.locator('[data-testid="confirm-delete-button"]').click()
  }

  async getRowCount() {
    return await this.rows.count()
  }
}
