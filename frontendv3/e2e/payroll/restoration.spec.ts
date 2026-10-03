import { test, expect } from '../fixtures'

test('restored payroll pages load the real backend and validate required input', async ({ page, loginAsAdmin }) => {
  await loginAsAdmin()
  await page.goto('/payroll')
  await expect(page.getByRole('heading', { name: 'Payroll Execution' })).toBeVisible()
  await page.getByTestId('preview-payroll-button').click()
  await expect(page.getByText('Select a valid date range with the end on or after the start.')).toBeVisible()
  await page.goto('/payroll-runs')
  await expect(page.getByRole('heading', { name: 'Payroll Runs', exact: true })).toBeVisible()
  await expect(page.getByRole('table')).toBeVisible()
  for (const [path, heading, add] of [
    ['sss', 'SSS Configuration', 'add-sss-button'],
    ['philhealth', 'PhilHealth Configuration', 'add-philhealth-button'],
    ['pagibig', 'Pag-IBIG Configuration', 'add-pagibig-button'],
    ['bir', 'BIR Configuration', 'add-bir-button'],
  ]) {
    await page.goto('/payroll-config/' + path)
    await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible()
    await expect(page.getByRole('table')).toBeVisible()
    await expect(page.getByText(/Failed to load/)).toHaveCount(0)
    await page.getByTestId(add).click()
    await expect(page.getByRole('dialog')).toBeVisible()
    await page.getByRole('dialog').getByRole('button', { name: 'Cancel', exact: true }).click()
  }
})
