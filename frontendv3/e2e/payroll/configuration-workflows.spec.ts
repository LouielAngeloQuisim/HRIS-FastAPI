import { test, expect } from '../fixtures'
import { apiUrl } from '../helpers/crud-journey'
import { StatutoryConfigurationPage } from '../pages/statutory-configuration.page'
import type { Page } from '@playwright/test'

async function headers(page: Page) {
  const token = (await page.context().cookies()).find(cookie => cookie.name === 'hris_at')?.value
  if (!token) throw new Error('Missing isolated QA session')
  return { Authorization: `Bearer ${token}` }
}

for (const [kind, fields, change] of [
  ['sss', { msc_min: '2000', msc_max: '35000', employer_ss: '1234.56', employer_ec: '30', employer_mpf: '120.25', employee_ss: '567.89', employee_mpf: '110.50' }, { employer_ss: '1500.75' }],
  ['philhealth', { salary_min: '10000', salary_max: '100000', rate: '5', employer_share: '2.5', employee_share: '2.5' }, { salary_min: '11000' }],
  ['pagibig', { salary_min: '1000', salary_max: '10000', employee_rate: '2', employer_rate: '2' }, { salary_min: '1100' }],
  ['bir', { period: 'semi_monthly', bracket_min: '100000.25', bracket_max: '', base_tax: '1234.56', excess_rate: '20' }, { base_tax: '1500.75' }],
] as const) {
  test(`${kind} configuration creates, reloads, edits and deactivates through UI`, async ({ page, loginAsAdmin }) => {
    await loginAsAdmin()
    const config = new StatutoryConfigurationPage(page, kind)
    await config.open()
    await page.getByTestId(`add-${kind}-button`).click()
    await config.fill({ ...fields, effective_date: '2028-01-01' })
    const created = await config.submit('POST')
    if (kind === 'sss') expect(created.employer_ss).toBe('1234.56')
    if (kind === 'bir') {
      expect(created.bracket_max).toBeNull()
      expect(created.period).toBe('semi_monthly')
    }
    await page.reload()
    await expect(page.getByTestId(`edit-${kind}-button-${created.id}`)).toBeVisible()
    await page.getByTestId(`edit-${kind}-button-${created.id}`).click()
    await config.fill(change)
    const saved = await config.submit('PATCH')
    for (const [key, value] of Object.entries(change)) expect(Number(saved[key])).toBe(Number(value))
    const list = await page.request.get(`${apiUrl}/payroll/${kind}-brackets/?period_type=`, { headers: await headers(page) })
    expect(await list.json()).toEqual(expect.arrayContaining([expect.objectContaining({ id: created.id })]))
    await config.deactivate(created.id)
    await page.reload()
    await expect(page.getByTestId(`edit-${kind}-button-${created.id}`)).toHaveCount(0)
    const archived = await page.request.get(`${apiUrl}/payroll/${kind}-brackets/?include_deleted=true&period_type=`, { headers: await headers(page) })
    expect(await archived.json()).toEqual(expect.arrayContaining([expect.objectContaining({ id: created.id, is_deleted: true })]))
  })
}

test('legacy payroll preview and generation stay blocked while readiness explains the remaining gates', async ({ page, loginAsAdmin }) => {
  await loginAsAdmin()
  const auth = await headers(page)
  const preview = await page.request.post(`${apiUrl}/payroll/runs/preview`, { headers: auth, data: { cutoff_type: 'monthly', date_from: '2026-10-01', date_to: '2026-10-31' } })
  expect(preview.status()).toBe(409)
  const generation = await page.request.post(`${apiUrl}/payroll/runs/generate`, { headers: auth, data: { cutoff_type: 'monthly', date_from: '2026-10-01', date_to: '2026-10-31', request_id: crypto.randomUUID() } })
  expect(generation.status()).toBe(409)
  await page.goto('/payroll')
  await expect(page.getByRole('heading', { name: 'Payroll readiness' })).toBeVisible()
  await expect(page.getByText(/statutory deductions.*remain disabled/i)).toBeVisible()
  await expect(page.getByTestId('payroll-prepare-draft-button')).toBeDisabled()
})

test('real permission rejection keeps statutory form values and shows one actionable error', async ({ page, loginAsAdmin, loginAsUser, logout }) => {
  await loginAsUser(process.env.E2E_USER_EMAIL || 'user@example.com', process.env.E2E_USER_PASSWORD || 'e2e-user-placeholder')
  const restrictedToken = (await page.context().cookies()).find(cookie => cookie.name === 'hris_at')!.value
  await logout()
  await loginAsAdmin()
  const config = new StatutoryConfigurationPage(page, 'sss')
  await config.open()
  await page.getByTestId('add-sss-button').click()
  await config.fill({ msc_min: '2000', msc_max: '35000', employer_ss: '1234.56', employer_ec: '30', employer_mpf: '120.25', employee_ss: '567.89', employee_mpf: '110.50', effective_date: '2028-01-01' })
  // Send the UI submission with the isolated view-only account's real token.
  // This exercises a real backend 403 rather than a fabricated failure body.
  await page.route('**/payroll/sss-brackets/', route => route.continue({ headers: { ...route.request().headers(), authorization: `Bearer ${restrictedToken}` } }))
  const rejected = page.waitForResponse(response => response.request().method() === 'POST' && response.url().includes('/payroll/sss-brackets/'))
  await page.getByTestId('sss-submit-button').click()
  expect((await rejected).status()).toBe(403)
  await expect(page.getByRole('alert')).toHaveCount(1)
  await expect(page.getByRole('alert')).toContainText(/permission|forbidden/i)
  await expect(page.getByTestId('sss-employer_ss-input')).toHaveValue('1234.56')
  await expect(page.getByTestId('sss-effective-date-input')).toHaveValue('2028-01-01')
  await expect(page.getByTestId('sss-submit-button')).toBeVisible()
})
