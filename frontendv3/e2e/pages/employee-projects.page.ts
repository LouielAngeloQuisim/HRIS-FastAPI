import { type Page, type Locator, expect } from '@playwright/test'

export class EmployeeProjectsPage {
  readonly page: Page
  readonly addButton: Locator
  readonly table: Locator
  readonly rows: Locator
  readonly employeeSelect: Locator
  readonly projectSelect: Locator
  readonly dateInput: Locator
  readonly renderedHoursInput: Locator
  readonly taskInput: Locator
  readonly assignedInput: Locator
  readonly submitButton: Locator
  readonly cancelButton: Locator

  constructor(page: Page) {
    this.page = page
    this.addButton = page.locator('[data-testid="add-employee-project-button"]')
    this.table = page.locator('table, [role="table"]')
    this.rows = page.locator('table tbody tr, [role="row"]')
    this.employeeSelect = page.locator('[data-testid="employee-project-employee-select"]')
    this.projectSelect = page.locator('[data-testid="employee-project-project-select"]')
    this.dateInput = page.locator('[data-testid="employee-project-date-input"]')
    this.renderedHoursInput = page.locator('[data-testid="employee-project-rendered-hours-input"]')
    this.taskInput = page.locator('[data-testid="employee-project-task-input"]')
    this.assignedInput = page.locator('[data-testid="employee-project-assigned-input"]')
    this.submitButton = page.locator('[data-testid="employee-project-submit-button"]')
    this.cancelButton = page.locator('[data-testid="cancel-delete-button"]')
  }

  async goto() {
    await this.page.goto('/employee-projects')
    await expect(this.table).toBeVisible({ timeout: 5000 })
  }

  async clickAdd() {
    await this.addButton.click()
  }

  async selectEmployee(label: string) {
    await this.employeeSelect.click()
    await this.page.locator(`[role="option"]:has-text("${label}")`).click()
  }

  async selectProject(label: string) {
    await this.projectSelect.click()
    await this.page.locator(`[role="option"]:has-text("${label}")`).click()
  }

  async fillDate(date: string) {
    await this.dateInput.fill(date)
  }

  async fillRenderedHours(hours: string) {
    await this.renderedHoursInput.fill(hours)
  }

  async fillTask(task: string) {
    await this.taskInput.fill(task)
  }

  async fillAssigned(assigned: string) {
    await this.assignedInput.fill(assigned)
  }

  async submit() {
    await this.submitButton.click()
  }

  async clickEditOnRow(index = 0) {
    const row = this.rows.nth(index)
    const editBtn = row.locator('[data-testid^="edit-employee-project-button"]')
    await editBtn.click()
  }

  async clickDeleteOnRow(index = 0) {
    const row = this.rows.nth(index)
    const deleteBtn = row.locator('[data-testid^="delete-employee-project-button"]')
    await deleteBtn.click()
  }

  async confirmDelete() {
    await this.page.locator('[data-testid="confirm-delete-button"]').click()
  }

  async getRowCount() {
    return await this.rows.count()
  }
}
