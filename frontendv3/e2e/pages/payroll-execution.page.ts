import { type Page, expect } from '@playwright/test'

export class PayrollExecutionPage {
  constructor(private readonly page: Page) {}

  async openExecution() {
    await this.page.goto('/payroll')
    await expect(this.page.getByText('Payroll Execution')).toBeVisible()
  }

  async selectEmployee(testId: 'employee-filter-select' | 'salary-employee-select', option: RegExp) {
    await this.page.getByTestId(testId).click()
    await this.page.getByRole('option', { name: option }).click()
  }

  async previewPeriod(from: string, to: string) {
    await this.page.getByTestId('date-from-input').fill(from)
    await this.page.getByTestId('date-to-input').fill(to)
    await this.page.getByTestId('preview-payroll-button').click()
  }

  async openSalaryRecovery() {
    await this.page.getByTestId('open-salary-setup-button').click()
    await expect(this.page).toHaveURL(/\/payroll\/salary\/?$/)
  }

  async createSalary(basicRate: string, effectiveDate: string) {
    await this.page.getByTestId('add-salary-button').click()
    await this.page.getByTestId('salary-form-basic-rate-input').fill(basicRate)
    await this.page.getByTestId('salary-form-effective-date-input').fill(effectiveDate)
    const response = this.page.waitForResponse((candidate) =>
      candidate.request().method() === 'POST' && /\/payroll\/employees\/[^/]+\/salary$/.test(new URL(candidate.url()).pathname),
    )
    await this.page.getByTestId('salary-form-submit-button').click()
    return response
  }

  async generateReviewedPayroll() {
    await this.page.getByTestId('proceed-to-review-button').click()
    await expect(this.page.getByRole('heading', { name: 'Payroll Run Generated' })).toBeVisible()
  }
}
