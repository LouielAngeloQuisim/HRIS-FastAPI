import { expect, type Page } from '@playwright/test'

export class StatutoryConfigurationPage {
  constructor(readonly page: Page, readonly kind: string) {}

  async open() {
    await this.page.goto(`/payroll-config/${this.kind}`)
    await expect(this.page.getByRole('table')).toBeVisible()
  }

  async fill(fields: Record<string, string>) {
    for (const [field, value] of Object.entries(fields)) {
      if (field === 'period') await this.page.getByTestId(`${this.kind}-${field}-input`).selectOption(value)
      else await this.page.getByTestId(`${this.kind}-${field === 'effective_date' ? 'effective-date' : field}-input`).fill(value)
    }
  }

  async submit(method: 'POST' | 'PATCH') {
    const response = this.page.waitForResponse((response) => response.request().method() === method &&
      new URL(response.url()).pathname.includes(`/payroll/${this.kind}-brackets/`))
    await this.page.getByRole('dialog').getByRole('button', { name: method === 'POST' ? 'Create' : 'Update', exact: true }).click()
    const result = await response
    expect(result.status()).toBe(200)
    return result.json()
  }

  async deactivate(id: string) {
    await this.page.getByTestId(`delete-${this.kind}-button-${id}`).click()
    const response = this.page.waitForResponse((response) => response.request().method() === 'DELETE' && response.url().endsWith(id))
    await this.page.getByRole('dialog').getByRole('button', { name: 'Delete', exact: true }).click()
    expect((await response).status()).toBe(200)
    await expect(this.page.getByTestId(`delete-${this.kind}-button-${id}`)).toHaveCount(0)
  }
}
