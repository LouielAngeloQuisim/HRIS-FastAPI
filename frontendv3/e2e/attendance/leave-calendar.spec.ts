import { test, expect } from '../fixtures'
import { apiUrl } from '../helpers/crud-journey'

test('calendar shows an empty range and sends changed dates', async ({ page, loginAsAdmin }) => {
  await loginAsAdmin()
  const load = page.waitForResponse(r => r.url().startsWith(apiUrl) && r.url().includes('/leave-calendar') && r.request().method() === 'GET')
  await page.goto('/leave-calendar')
  const response = await load
  expect(response.status()).toBe(200)
  expect(await response.json()).toEqual([])
  await expect(page.getByText('No leave events found for the selected range.')).toBeVisible()
  await page.getByTestId('leave-calendar-from-date').fill('2026-01-01')
  await page.getByTestId('leave-calendar-to-date').fill('2026-12-31')
  const filtered = page.waitForResponse(r => r.url().startsWith(apiUrl) && r.url().includes('/leave-calendar') && new URL(r.url()).searchParams.get('to_date') === '2026-12-31')
  await page.getByTestId('leave-calendar-apply-button').click()
  expect((await filtered).status()).toBe(200)
  await expect(page.getByTestId('leave-calendar-from-date')).toHaveValue('2026-01-01')
})
