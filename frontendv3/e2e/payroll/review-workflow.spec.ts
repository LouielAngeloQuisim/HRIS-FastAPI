import { expect, test } from '../fixtures'
import { apiUrl, createParent } from '../helpers/crud-journey'
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

test('blocked attendance payroll draft can be explicitly excluded with a reason', async ({ page, loginAsAdmin }) => {
  await loginAsAdmin()
  const unique = Date.now().toString(36)
  const employee = await createParent(page, 'employees', {
    employee_code: `PAY${unique}`,
    first_name: 'QA Payroll',
    last_name: unique,
    birthdate: '1990-01-01',
    date_hired: '2026-01-01',
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
      monthly_salary_proration: 'scheduled_workday_fraction',
      monthly_holiday_pay_divisor: '22',
      daily_partial_work: 'pro_rated',
      monthly_partial_work: 'deduct_after_grace',
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
  // The migration supplies the complete official 2025 SSS schedule. Do not
  // insert overlapping fake SSS bands into this integration journey.
  // Published PhilHealth and Pag-IBIG schedules are seeded by migration;
  // this workflow verifies the configured schedules without fake overlaps.
  const confirmedPolicy = await page.request.post(`${apiUrl}/payroll/policies/${policy.id}/confirm`, {
    headers: await bearer(page),
  })
  expect(
    confirmedPolicy.status(),
    `Confirm isolated QA payroll policy: ${await confirmedPolicy.text()}`,
  ).toBe(200)

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
  const shift = await createParent(page, 'shifts', {
    code: `QA${unique}`,
    name: `QA weekday shift ${unique}`,
    start_time: '08:00',
    end_time: '17:00',
    lunch_break_duration: 60,
    total_hours_minus_lunch: 480,
    days_of_week: ['1', '2', '3', '4', '5'],
  })
  const shiftAssignment = await page.request.post(`${apiUrl}/employee-shift-assignments/`, {
    headers: await bearer(page),
    data: { employee_id: employee.id, shift_id: shift.id, effective_from: '2020-01-01' },
  })
  expect(shiftAssignment.status(), 'Assign weekday payroll shift').toBe(201)
  for (let day = 1; day <= 31; day++) {
    const workDate = new Date(Date.UTC(2026, 9, day))
    if (workDate.getUTCDay() === 0 || workDate.getUTCDay() === 6) continue
    const date = workDate.toISOString().slice(0, 10)
    const punch = await page.request.post(`${apiUrl}/daily-time-records/`, {
      headers: await bearer(page),
      data: {
        employee_id: employee.id,
        shift_id: shift.id,
        login_date: `${date}T00:00:00Z`,
        logout_date: `${date}T09:00:00Z`,
      },
    })
    expect(punch.status(), `Create resolved attendance for ${date}`).toBe(201)
  }

  const configuredPeriods = await page.request.get(
    `${apiUrl}/payroll/pay-groups/${group.id}/periods?month=2026-10`,
    { headers: await bearer(page) },
  )
  expect(configuredPeriods.status(), await configuredPeriods.text()).toBe(200)
  const periodRows = await configuredPeriods.json()
  expect(periodRows.map((row: { date_from: string; date_to: string }) => [row.date_from, row.date_to])).toContainEqual([
    '2026-10-16',
    '2026-10-31',
  ])

  const prepared = await page.request.post(`${apiUrl}/payroll/runs/prepare-attendance-draft`, {
    headers: await bearer(page),
    data: { pay_group_id: group.id, date_from: '2026-10-16', date_to: '2026-10-31' },
  })
  expect(prepared.status(), `Prepare isolated payroll draft: ${await prepared.text()}`).toBe(201)
  const draft = await prepared.json()
  expect(draft.workflow_status).toBe('draft')

  await page.goto(`/payroll-runs/${draft.id}`)
  await expect(page.getByRole('heading', { name: 'Payroll review' })).toBeVisible()
  await expect(
    page
      .getByText("Enter and verify this employee's tax classification and opening year-to-date amounts before payroll review.")
      .first(),
  ).toBeVisible()
  await page.getByRole('button', { name: 'Start employee review' }).click()
  await expect(page.getByRole('status')).toContainText('exclude a blocked employee with a reason')
  const target = draft.entries.find((candidate: { employee_id: string }) => candidate.employee_id === employee.id)
  expect(target, 'The prepared run must include this test employee').toBeTruthy()
  const exclusionReason = 'Missing verified tax-year opening balance; exclude from this run'
  for (const candidate of draft.entries) {
    if (candidate.employee_id === employee.id) continue
    const response = await page.request.post(
      `${apiUrl}/payroll/runs/${draft.id}/entries/${candidate.id}/review`,
      {
        headers: await bearer(page),
        data: {
          action: 'excluded',
          expected_input_fingerprint: candidate.input_fingerprint,
          reason: 'No effective assignment to this QA pay group; explicitly excluded from isolated run',
        },
      },
    )
    expect(response.status(), `Disposition unrelated unassigned QA entry ${candidate.id}: ${await response.text()}`).toBe(200)
  }
  await page.reload()
  const targetCard = page.getByTestId(`payroll-entry-${target.id}`)
  await targetCard.getByRole('textbox', { name: 'Exclusion reason' }).fill(exclusionReason)
  await targetCard.getByRole('button', { name: 'Exclude with reason' }).click()
  await expect(targetCard.getByText('Review state: excluded')).toBeVisible()

  const saved = await page.request.get(`${apiUrl}/payroll/runs/${draft.id}`, { headers: await bearer(page) })
  expect(saved.status()).toBe(200)
  const savedRun = await saved.json()
  expect(savedRun.workflow_status).toBe('ready_for_finalization')
  const entry = savedRun.entries.find((candidate: { employee_id: string }) => candidate.employee_id === employee.id)
  expect(entry.review_reason).toBe(exclusionReason)
  expect(entry.review_state).toBe('excluded')
  expect(entry.blockers.map((blocker: { code: string }) => blocker.code)).toContain('bir_ytd_unavailable')
  expect(
    entry.input_snapshot.monthly_contributions,
    JSON.stringify({ blockers: entry.blockers, snapshot: entry.input_snapshot }),
  ).toBeTruthy()
  expect(entry.input_snapshot.monthly_contributions.month).toBe('2026-10')
  expect(entry.deductions.sss_employee).toBe('1300.00')
  expect(entry.deductions.philhealth_employee).toBe('650.00')
  expect(entry.deductions.pagibig_employee).toBe('200.00')
  expect(entry.deductions.employer_contributions).toEqual({
    sss: '2630.00',
    philhealth: '650.00',
    pagibig: '200.00',
  })
})
