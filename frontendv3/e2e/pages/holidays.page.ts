import { type Page, type Locator, expect } from '@playwright/test'

export class HolidaysPage {
  readonly page: Page
  readonly addButton: Locator
  readonly table: Locator
  readonly rows: Locator
  readonly codeInput: Locator
  readonly nameInput: Locator
  readonly monthDayInput: Locator
  readonly typeSelect: Locator
  readonly regionInput: Locator
  readonly recurringSwitch: Locator
  readonly submitButton: Locator
  readonly cancelButton: Locator

  constructor(page: Page) {
    this.page = page
    this.addButton = page.locator('[data-testid="holiday-add-button"]')
    this.table = page.locator('table, [role="table"]')
    this.rows = page.locator('table tbody tr, [role="row"]')
    this.codeInput = page.locator('[data-testid="holiday-code-input"]')
    this.nameInput = page.locator('[data-testid="holiday-name-input"]')
    this.monthDayInput = page.locator('[data-testid="holiday-month-day-input"]')
    this.typeSelect = page.locator('[data-testid="holiday-type-select"]')
    this.regionInput = page.locator('[data-testid="holiday-region-input"]')
    this.recurringSwitch = page.locator('[data-testid="holiday-recurring-switch"]')
    this.submitButton = page.locator('[data-testid="holiday-submit-button"]')
    this.cancelButton = page.locator('[data-testid="cancel-delete-button"]')
  }

  async goto() {
    await this.page.goto('/holidays')
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

  async fillMonthDay(monthDay: string) {
    await this.monthDayInput.fill(monthDay)
  }

  async selectType(type: string) {
    await this.typeSelect.click()
    await this.page.locator(`[role="option"]:has-text("${type}")`).click()
  }

  async fillRegion(region: string) {
    await this.regionInput.fill(region)
  }

  async toggleRecurring() {
    await this.recurringSwitch.click()
  }

  async submit() {
    await this.submitButton.click()
  }

  async clickEditOnRow(index = 0) {
    const row = this.rows.nth(index)
    const editBtn = row.locator('[data-testid^="edit-holiday-button"]')
    await editBtn.click()
  }

  async clickDeleteOnRow(index = 0) {
    const row = this.rows.nth(index)
    const deleteBtn = row.locator('[data-testid^="delete-holiday-button"]')
    await deleteBtn.click()
  }

  async confirmDelete() {
    await this.page.locator('[data-testid="confirm-delete-button"]').click()
  }

  async getRowCount() {
    return await this.rows.count()
  }
}
