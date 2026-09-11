import { type Page, type Locator, expect } from '@playwright/test'

export class EmpTasksPage {
  readonly page: Page
  readonly addButton: Locator
  readonly table: Locator
  readonly rows: Locator
  readonly employeeProjectSelect: Locator
  readonly taskDescInput: Locator
  readonly renderedHoursInput: Locator
  readonly assignedHoursInput: Locator
  readonly dateInput: Locator
  readonly approvedInput: Locator
  readonly adjustedInput: Locator
  readonly submitButton: Locator
  readonly cancelButton: Locator

  constructor(page: Page) {
    this.page = page
    this.addButton = page.locator('[data-testid="add-emp-task-button"]')
    this.table = page.locator('table, [role="table"]')
    this.rows = page.locator('table tbody tr, [role="row"]')
    this.employeeProjectSelect = page.locator('[data-testid="emp-task-employee-project-select"]')
    this.taskDescInput = page.locator('[data-testid="emp-task-task-desc-input"]')
    this.renderedHoursInput = page.locator('[data-testid="emp-task-rendered-hours-input"]')
    this.assignedHoursInput = page.locator('[data-testid="emp-task-assigned-hours-input"]')
    this.dateInput = page.locator('[data-testid="emp-task-date-input"]')
    this.approvedInput = page.locator('[data-testid="emp-task-approved-input"]')
    this.adjustedInput = page.locator('[data-testid="emp-task-adjusted-input"]')
    this.submitButton = page.locator('[data-testid="emp-task-submit-button"]')
    this.cancelButton = page.locator('[data-testid="cancel-delete-button"]')
  }

  async goto() {
    await this.page.goto('/emp-tasks')
    await expect(this.table).toBeVisible({ timeout: 5000 })
  }

  async clickAdd() {
    await this.addButton.click()
  }

  async selectEmployeeProject(label: string) {
    await this.employeeProjectSelect.click()
    await this.page.locator(`[role="option"]:has-text("${label}")`).click()
  }

  async fillTaskDesc(desc: string) {
    await this.taskDescInput.fill(desc)
  }

  async fillRenderedHours(hours: string) {
    await this.renderedHoursInput.fill(hours)
  }

  async fillAssignedHours(hours: string) {
    await this.assignedHoursInput.fill(hours)
  }

  async fillDate(date: string) {
    await this.dateInput.fill(date)
  }

  async fillApproved(approved: string) {
    await this.approvedInput.fill(approved)
  }

  async fillAdjusted(adjusted: string) {
    await this.adjustedInput.fill(adjusted)
  }

  async submit() {
    await this.submitButton.click()
  }

  async clickEditOnRow(index = 0) {
    const row = this.rows.nth(index)
    const editBtn = row.locator('[data-testid^="edit-emp-task-button"]')
    await editBtn.click()
  }

  async clickDeleteOnRow(index = 0) {
    const row = this.rows.nth(index)
    const deleteBtn = row.locator('[data-testid^="delete-emp-task-button"]')
    await deleteBtn.click()
  }

  async confirmDelete() {
    await this.page.locator('[data-testid="confirm-delete-button"]').click()
  }

  async getRowCount() {
    return await this.rows.count()
  }
}
