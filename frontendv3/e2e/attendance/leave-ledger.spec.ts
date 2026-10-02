import { test, expect } from '../fixtures'

test('ledger shell exposes year and refresh controls before a policy is selected', async ({ page, loginAsAdmin }) => {
  await loginAsAdmin()
  await page.goto('/leave-ledger')
  await expect(page.getByRole('heading', { name: 'Leave Ledger', exact: true })).toBeVisible()
  await expect(page.getByTestId('leave-ledger-year-input')).toBeVisible()
  await page.getByTestId('leave-ledger-year-input').fill('2025')
  await expect(page.getByTestId('leave-ledger-year-input')).toHaveValue('2025')
  await expect(page.getByTestId('leave-ledger-refresh-button')).toBeEnabled()
})
