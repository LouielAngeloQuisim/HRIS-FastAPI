import { expect, test } from '../fixtures'
import { apiUrl, assignEmployeeShift, createParent } from '../helpers/crud-journey'
import type { Page } from '@playwright/test'

async function bearer(page: Page) {
  const token = (await page.context().cookies()).find(cookie => cookie.name === 'hris_at')?.value
  if (!token) throw new Error('Missing isolated QA session')
  return { Authorization: `Bearer ${token}` }
}

async function createResource(page: Page, path: string, data: Record<string, unknown>) {
  const response = await page.request.post(`${apiUrl}/payroll/${path}`, {
    headers: await bearer(page),
    data,
  })
  expect([200, 201], `Create payroll fixture ${path}: ${response.status()}`).toContain(response.status())
  return response.json()
}

test('blocked attendance payroll draft is visible in the review screen but cannot be reviewed', async ({ page, loginAsAdmin }) => {
  await loginAsAdmin()
  const unique = Date.now().toString(36)
  const employee = await createParent(page, 'employees', {
    employee_code: `PAY${unique}`,
    first_name: 'QA Payroll',
    last_name: unique,
    birthdate: '1990-01-01',
    email: `qa-payroll-${unique}@example.test`,
  })
  const group = await createResource(page, 'pay-groups', {
    code: `PAY${unique}`,
    name: `QA twice-monthly ${unique}`,
    cadence: 'semi_monthly',
    first_period_end_day: 15,
    second_period_end_day: 31,
    payment_offset_days: 0,
    weekend_rule: 'next_business_day',
  })
  const policy = await createResource(page, 'policies', {
    effective_from: '2026-10-01',
    policy: {
      timezone: 'Asia/Manila',
      monthly_divisor: '22',
      daily_partial_work: 'pro_rated',
      paid_leave: false,
      paid_holidays: false,
      break_minutes: 60,
      grace_minutes: 0,
      overtime_rule: { multiplier: '1.25' },
      premium_rules: { enabled: false },
      allowance_tax_treatment: { default: 'taxable' },
      rounding_mode: 'half_up',
      contribution_collection: { frequency: 'once_monthly', collection_period: 'last_period' },
      statutory_sources_reviewed: [
        'https://www.bir.gov.ph/',
        'https://www.sss.gov.ph/sss-contribution-table/',
        'https://www.philhealth.gov.ph/advisories/2025/PA2025-0002.pdf',
        'https://www.pagibigfund.gov.ph/document/pdf/payments/AcceptingPagIBIGPaymentsThroughOTC_24%20JAN%202025.pdf',
      ],
    },
  })
  // The policy confirmation gate requires complete effective schedules. These
  // deliberately synthetic rows only exercise workflow wiring; they are not
  // statutory rates and cannot unblock the payroll calculation itself.
  await createResource(page, 'sss-brackets/', {
    msc_min: '0.01', msc_max: '35000.00', employer_ss: '0', employer_ec: '0',
    employer_mpf: '0', employee_ss: '0', employee_mpf: '0', effective_date: '2026-10-01',
  })
  await createResource(page, 'philhealth-brackets/', {
    salary_min: '10000.00', salary_max: '100000.00', rate: '5',
    employer_share: '2.5', employee_share: '2.5', effective_date: '2026-10-01',
  })
  await createResource(page, 'pagibig-brackets/', {
    salary_min: '0.01', salary_max: '1000000.00', employee_rate: '2',
    employer_rate: '2', effective_date: '2026-10-01',
  })
  for (const period of ['daily', 'weekly', 'semi_monthly', 'monthly']) {
    await createResource(page, 'bir-brackets/', {
      period, bracket_min: '0', bracket_max: null, base_tax: '0',
      excess_rate: '0', effective_date: '2026-10-01',
    })
  }
  const confirmedPolicy = await page.request.post(`${apiUrl}/payroll/policies/${policy.id}/confirm`, {
    headers: await bearer(page),
  })
  expect(confirmedPolicy.status(), 'Confirm isolated QA payroll policy').toBe(200)

  const salary = await page.request.post(`${apiUrl}/payroll/employees/${employee.id}/salary`, {
    headers: await bearer(page),
    data: {
      employee_id: employee.id,
      basic_rate: '26000.00',
      currency: 'PHP',
      effective_date: '2026-10-01',
      pay_type: 'monthly',
      overtime_rate: '1.25',
      absent_penalty_rate: '1.00',
      non_taxable_allowance: '0.00',
      de_minimis_monthly: {},
      thirteenth_month_exempt_portion: '90000.00',
      is_active: true,
    },
  })
  expect(salary.status(), 'Create salary fixture').toBe(200)

  const groupAssignment = await page.request.post(`${apiUrl}/payroll/pay-group-assignments`, {
    headers: await bearer(page),
    data: { employee_id: employee.id, pay_group_id: group.id, effective_from: '2026-10-01' },
  })
  expect(groupAssignment.status(), 'Assign employee to isolated pay group').toBe(201)
  const shift = await assignEmployeeShift(page, employee.id)
  const punch = await page.request.post(`${apiUrl}/daily-time-records/`, {
    headers: await bearer(page),
    data: {
      employee_id: employee.id,
      shift_id: shift.id,
      login_date: '2026-10-01T00:00:00Z',
      logout_date: '2026-10-01T09:00:00Z',
    },
  })
  expect(punch.status()).toBe(201)

  const prepared = await page.request.post(`${apiUrl}/payroll/runs/prepare-attendance-draft`, {
    headers: await bearer(page),
    data: { pay_group_id: group.id, date_from: '2026-10-01', date_to: '2026-10-15' },
  })
  expect(prepared.status(), 'Prepare isolated payroll draft').toBe(201)
  const draft = await prepared.json()
  expect(draft.workflow_status).toBe('draft')

  await page.goto(`/payroll-runs/${draft.id}`)
  await expect(page.getByRole('heading', { name: 'Payroll review' })).toBeVisible()
  await expect(page.getByText(/Approved statutory schedule amounts and BIR annualization\/YTD inputs are not yet calculated/)).toBeVisible()
  await page.getByRole('button', { name: 'Start employee review' }).click()
  await expect(page.getByText('Resolve all payroll blockers before opening review.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Mark reviewed' })).toHaveCount(0)

  const saved = await page.request.get(`${apiUrl}/payroll/runs/${draft.id}`, { headers: await bearer(page) })
  expect(saved.status()).toBe(200)
  const savedRun = await saved.json()
  expect(savedRun.workflow_status).toBe('draft')
  expect(savedRun.entries[0].review_state).toBe('blocked')
  expect(savedRun.entries[0].blockers.map((blocker: { code: string }) => blocker.code)).toContain('statutory_calculation_unavailable')
})
