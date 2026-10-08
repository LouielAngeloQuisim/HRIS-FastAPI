import { expect, test } from '../fixtures'
import { apiUrl, createParent } from '../helpers/crud-journey'
import type { Page } from '@playwright/test'

const FINALIZER_PASSWORD = 'e2e-payroll-finalizer-placeholder'

async function bearer(page: Page) {
  const token = (await page.context().cookies()).find(cookie => cookie.name === 'hris_at')?.value
  if (!token) throw new Error('Missing isolated QA session')
  return { Authorization: `Bearer ${token}` }
}

async function createPayrollResource(page: Page, path: string, data: Record<string, unknown>) {
  const response = await page.request.post(`${apiUrl}/payroll/${path}`, {
    headers: await bearer(page),
    data,
  })
  expect([200, 201], `Create payroll fixture ${path}: ${await response.text()}`).toContain(response.status())
  return response.json()
}

test('fictional employee payroll is reviewed, separately finalized and frozen for disabled email delivery', async ({
  page,
  loginAsAdmin,
  loginAsUser,
  logout,
}) => {
  await loginAsAdmin()
  const unique = Date.now().toString(36)
  const employee = await createParent(page, 'employees', {
    employee_code: `FNP${unique}`,
    first_name: 'QA Fictional',
    last_name: unique,
    birthdate: '1990-01-01',
    date_hired: '2026-01-01',
    email: `qa-finalized-${unique}@example.test`,
  })

  const group = await createPayrollResource(page, 'pay-groups', {
    code: `FNP${unique}`,
    name: `QA semi-monthly ${unique}`,
    cadence: 'semi_monthly',
    first_period_end_day: 15,
    second_period_end_day: 31,
    payment_offset_days: 0,
    weekend_rule: 'next_business_day',
  })
  const policy = await createPayrollResource(page, 'policies', {
    effective_from: '2026-11-01',
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
        'https://www.bir.gov.ph/WithHoldingTax?q=RDO',
        'https://www.sss.gov.ph/sss-contribution-table/',
        'https://www.philhealth.gov.ph/advisories/2025/PA2025-0002.pdf',
        'https://www.pagibigfund.gov.ph/document/pdf/circulars/provident/Circular%20No.%20460%20-%20Guidelines%20on%20the%20Pag-IBIG%20Fund%27s%20Implementation%20of%20Increase%20in%20the%20MFS%20Effective%20February%202024.pdf',
      ],
    },
  })
  const confirmed = await page.request.post(`${apiUrl}/payroll/policies/${policy.id}/confirm`, {
    headers: await bearer(page),
  })
  expect(confirmed.status(), await confirmed.text()).toBe(200)

  const salary = await page.request.post(`${apiUrl}/payroll/employees/${employee.id}/salary`, {
    headers: await bearer(page),
    data: {
      employee_id: employee.id,
      basic_rate: '26000.00',
      currency: 'PHP',
      effective_date: '2026-11-01',
      pay_type: 'monthly',
      overtime_rate: '1.25',
      absent_penalty_rate: '1.00',
      non_taxable_allowance: '0.00',
      de_minimis_monthly: {},
      thirteenth_month_exempt_portion: '90000.00',
      is_active: true,
    },
  })
  expect(salary.status(), await salary.text()).toBe(200)
  const groupAssignment = await page.request.post(`${apiUrl}/payroll/pay-group-assignments`, {
    headers: await bearer(page),
    data: { employee_id: employee.id, pay_group_id: group.id, effective_from: '2026-11-01' },
  })
  expect(groupAssignment.status(), await groupAssignment.text()).toBe(201)

  const shift = await createParent(page, 'shifts', {
    code: `FNP${unique}`,
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
  expect(shiftAssignment.status(), await shiftAssignment.text()).toBe(201)

  const attendanceRows = ['employee_code,login_date,logout_date']
  // Monthly SSS/PhilHealth/Pag-IBIG assessment requires the complete month,
  // even though this run covers only the second semi-monthly pay period.
  for (let day = 1; day <= 30; day++) {
    const workDate = new Date(Date.UTC(2026, 10, day))
    if (workDate.getUTCDay() === 0 || workDate.getUTCDay() === 6) continue
    const date = workDate.toISOString().slice(0, 10)
    attendanceRows.push(`${employee.employee_code},${date}T00:00:00Z,${date}T09:00:00Z`)
  }
  // Exercise the actual CSV import and review UI as the attendance source for
  // the payroll run, rather than creating DTR records directly through the API.
  await page.goto('/daily-time-records')
  await page.getByTestId('import-dtr-csv-button').click()
  await page.getByPlaceholder(/employee_code/).fill(attendanceRows.join('\n'))
  const importing = page.waitForResponse(response =>
    response.url().includes('/daily-time-records/import-batches/commit') && response.request().method() === 'POST',
  )
  await page.getByTestId('csv-import-submit-button').click()
  const importResponse = await importing
  expect(importResponse.status(), await importResponse.text()).toBe(200)
  await expect(page.getByText(`${attendanceRows.length - 1} succeeded`)).toBeVisible()
  await page.getByTestId('csv-import-close-button').click()

  const declaration = await page.request.put(
    `${apiUrl}/payroll/employees/${employee.id}/tax-year-declarations/2026`,
    {
      headers: await bearer(page),
      data: {
        tax_classification: 'ordinary',
        opening_as_of: '2026-10-01',
        taxable_compensation_ytd: '0.00',
        tax_withheld_ytd: '0.00',
        previous_employer_included: false,
        source_reference: 'Fictional isolated QA opening balance',
        is_verified: true,
      },
    },
  )
  expect(declaration.status(), await declaration.text()).toBe(200)

  const prepared = await page.request.post(`${apiUrl}/payroll/runs/prepare-attendance-draft`, {
    headers: await bearer(page),
    data: { pay_group_id: group.id, date_from: '2026-11-16', date_to: '2026-11-30' },
  })
  expect(prepared.status(), await prepared.text()).toBe(201)
  const draft = await prepared.json()
  const preparedEntry = draft.entries.find((entry: { employee_id: string }) => entry.employee_id === employee.id)
  expect(preparedEntry, 'The fictional employee must be included').toBeTruthy()
  expect(preparedEntry.blockers, JSON.stringify(preparedEntry.blockers)).toEqual([])

  await page.goto(`/payroll-runs/${draft.id}`)
  await expect(page.getByRole('heading', { name: 'Payroll review' })).toBeVisible()
  await page.getByRole('button', { name: 'Start employee review' }).click()
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
  const targetCard = page.getByTestId(`payroll-entry-${preparedEntry.id}`)
  await targetCard.getByRole('button', { name: 'Mark reviewed' }).click()
  await expect(targetCard.getByText('Review state: reviewed')).toBeVisible()

  const finalizerEmail = `payroll-finalizer-${unique}@example.com`
  const role = await page.request.post(`${apiUrl}/rbac/roles`, {
    headers: await bearer(page),
    data: { code: `F${unique}`, name: `QA payroll finalizer ${unique}` },
  })
  expect(role.status(), await role.text()).toBe(201)
  const finalizerRole = await role.json()
  const permissions = await page.request.patch(`${apiUrl}/rbac/roles/${finalizerRole.id}`, {
    headers: await bearer(page),
    data: { permissions: ['payroll.view', 'payroll.approve'] },
  })
  expect(permissions.status(), await permissions.text()).toBe(200)
  const userResponse = await page.request.post(`${apiUrl}/users/`, {
    headers: await bearer(page),
    data: { email: finalizerEmail, password: FINALIZER_PASSWORD, is_superuser: false },
  })
  expect(userResponse.status(), await userResponse.text()).toBe(200)
  const finalizer = await userResponse.json()
  const assigned = await page.request.post(`${apiUrl}/users/${finalizer.id}/role`, {
    headers: await bearer(page),
    data: { role_code: finalizerRole.code },
  })
  expect(assigned.status(), await assigned.text()).toBe(200)

  await logout()
  await loginAsUser(finalizerEmail, FINALIZER_PASSWORD)
  await page.goto(`/payroll-runs/${draft.id}`)
  await expect(page.getByRole('button', { name: 'Finalize and schedule payslips' })).toBeEnabled()
  page.once('dialog', dialog => dialog.accept())
  await page.getByRole('button', { name: 'Finalize and schedule payslips' }).click()
  await expect(page.getByText('Workflow: finalized')).toBeVisible()
  await expect(page.getByText('Email delivery is disabled by system configuration.')).toBeVisible()

  const saved = await page.request.get(`${apiUrl}/payroll/runs/${draft.id}`, { headers: await bearer(page) })
  expect(saved.status(), await saved.text()).toBe(200)
  const finalized = await saved.json()
  expect(finalized.workflow_status).toBe('finalized')
  expect(finalized.finalized_by).toBe(finalizer.id)
  expect(finalized.finalized_by).not.toBe(finalized.created_by)
  const finalizedEntry = finalized.entries.find((entry: { id: string }) => entry.id === preparedEntry.id)
  expect(finalizedEntry).toBeDefined()
  expect(finalizedEntry.review_state).toBe('reviewed')
  expect(finalizedEntry.reviewed_by).not.toBe(finalized.finalized_by)
  expect(finalizedEntry.net_pay).toBe(preparedEntry.net_pay)
  const delivery = await page.request.get(`${apiUrl}/payroll/runs/${draft.id}/delivery-status`, {
    headers: await bearer(page),
  })
  expect(delivery.status(), await delivery.text()).toBe(200)
  const jobs = await delivery.json()
  expect(jobs).toHaveLength(1)
  expect(jobs[0].status).toBe('scheduled')
  const payslip = await page.request.get(
    `${apiUrl}/payroll/runs/${draft.id}/entries/${preparedEntry.id}/payslip.pdf`,
    { headers: await bearer(page) },
  )
  expect(payslip.status(), await payslip.text()).toBe(200)
  expect(payslip.headers()['content-type']).toContain('application/pdf')
  expect(Buffer.from(await payslip.body()).subarray(0, 5).toString()).toBe('%PDF-')
})
