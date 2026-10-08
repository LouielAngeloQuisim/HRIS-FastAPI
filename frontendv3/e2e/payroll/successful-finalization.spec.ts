import { expect, test } from '../fixtures'
import { apiUrl, createParent } from '../helpers/crud-journey'
import type { Page } from '@playwright/test'

const FINALIZER_PASSWORD = 'e2e-payroll-finalizer-placeholder'
let finalizedPayrollCorrectionFixture: {
  employeeId: string
  employeeCode: string
  groupId: string
  runId: string
  entryId: string
  netPay: string
  unique: string
} | null = null

test.describe.configure({ mode: 'serial' })

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

test('fictional attendance payroll is independently reviewed, finalized, and scheduled for payslips', async ({
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
    email: null,
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

  // Recover this employee from the missing-salary roster through the bulk UI.
  await page.goto('/payroll/salary')
  await page.getByLabel('Only employees without an effective salary').check()
  await expect(page.getByLabel(`Select ${employee.employee_code}`)).toBeVisible()
  await page.getByLabel(`Select ${employee.employee_code}`).check()
  await page.getByLabel(`${employee.employee_code} basic rate`).fill('26000.00')
  await page.getByLabel(`${employee.employee_code} salary basis`).selectOption('monthly')
  await page.getByLabel(`${employee.employee_code} overtime rate`).fill('1.25')
  await page.getByLabel(`${employee.employee_code} allowance`).fill('0.00')
  await page.getByLabel('Bulk effective date').fill('2026-11-01')
  const salaryPreflight = page.waitForResponse(response =>
    response.url().includes('/payroll/salaries/bulk/preflight') && response.request().method() === 'POST',
  )
  await page.getByRole('button', { name: 'Validate batch' }).click()
  const salaryPreflightResponse = await salaryPreflight
  expect(salaryPreflightResponse.status(), await salaryPreflightResponse.text()).toBe(200)
  expect((await salaryPreflightResponse.json()).valid).toBe(true)
  const salaryCommit = page.waitForResponse(response =>
    response.url().includes('/payroll/salaries/bulk/commit') && response.request().method() === 'POST',
  )
  await page.getByRole('button', { name: 'Save selected salaries' }).click()
  const salaryResponse = await salaryCommit
  expect(salaryResponse.status(), await salaryResponse.text()).toBe(200)
  const salaryReadback = await page.request.get(
    `${apiUrl}/payroll/employees/${employee.id}/salary`,
    { headers: await bearer(page) },
  )
  expect(salaryReadback.status(), await salaryReadback.text()).toBe(200)
  expect(await salaryReadback.json()).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        basic_rate: '26000.00',
        effective_date: '2026-11-01',
        pay_type: 'monthly',
      }),
    ]),
  )
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

  // Exercise the HR payroll readiness, earnings preview, and draft preparation
  // screens. The API readbacks below verify persisted values and finalization.
  await page.goto('/payroll')
  await page.getByTestId('payroll-pay-group-select').click()
  await page.getByRole('option', { name: new RegExp(`QA semi-monthly ${unique}`) }).click()
  await page.getByTestId('payroll-period-from').fill('2026-11-16')
  await page.getByTestId('payroll-period-to').fill('2026-11-30')
  const readiness = page.waitForResponse(response =>
    response.url().includes('/payroll/runs/preflight') && response.request().method() === 'GET',
  )
  await page.getByTestId('payroll-preflight-button').click()
  expect((await readiness).status()).toBe(200)
  await expect(page.getByText('Ready for calculation review')).toBeVisible()
  const earningsPreview = page.waitForResponse(response =>
    response.url().includes('/payroll/runs/attendance-calculation-preview') && response.request().method() === 'GET',
  )
  await page.getByTestId('payroll-attendance-preview-button').click()
  expect((await earningsPreview).status()).toBe(200)
  await expect(page.getByRole('region', { name: 'Attendance earnings preview' })).toContainText(employee.employee_code)
  const preparing = page.waitForResponse(response =>
    response.url().includes('/payroll/runs/prepare-attendance-draft') && response.request().method() === 'POST',
  )
  await page.getByTestId('payroll-prepare-draft-button').click()
  const prepareResponse = await preparing
  expect(prepareResponse.status(), await prepareResponse.text()).toBe(201)
  const draft = await prepareResponse.json()
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

  const saved = await page.request.get(`${apiUrl}/payroll/runs/${draft.id}`, { headers: await bearer(page) })
  expect(saved.status(), await saved.text()).toBe(200)
  const ready = await saved.json()
  expect(ready.workflow_status).toBe('ready_for_finalization')
  expect(ready.finalized_by).toBeNull()
  expect(ready.frozen_snapshot ?? null).toBeNull()
  const reviewedEntry = ready.entries.find((entry: { id: string }) => entry.id === preparedEntry.id)
  expect(reviewedEntry).toBeDefined()
  expect(reviewedEntry.review_state).toBe('reviewed')
  expect(reviewedEntry.calculation_version).toBe('attendance-v1')
  expect(reviewedEntry.earnings.provisional).toBe(false)
  const finalizing = page.waitForResponse(response =>
    response.url().includes(`/payroll/runs/${draft.id}/finalize`) && response.request().method() === 'POST',
  )
  page.once('dialog', dialog => dialog.accept())
  await page.getByRole('button', { name: 'Finalize and schedule payslips' }).click()
  const finalizeResponse = await finalizing
  expect(finalizeResponse.status(), await finalizeResponse.text()).toBe(200)
  await expect(page.getByText('Workflow: finalized')).toBeVisible()
  const finalizedReadback = await page.request.get(`${apiUrl}/payroll/runs/${draft.id}`, { headers: await bearer(page) })
  expect(finalizedReadback.status(), await finalizedReadback.text()).toBe(200)
  const finalized = await finalizedReadback.json()
  expect(finalized.workflow_status).toBe('finalized')
  expect(finalized.finalized_by).toBe(finalizer.id)
  const finalizedEntry = finalized.entries.find((entry: { id: string }) => entry.id === preparedEntry.id)
  expect(finalizedEntry.review_state).toBe('reviewed')
  const delivery = await page.request.get(`${apiUrl}/payroll/runs/${draft.id}/delivery-status`, {
    headers: await bearer(page),
  })
  expect(delivery.status(), await delivery.text()).toBe(200)
  const jobs = await delivery.json()
  expect(jobs).toEqual(expect.arrayContaining([
    expect.objectContaining({ payroll_entry_id: preparedEntry.id, status: 'blocked_email' }),
  ]))

  // Recover a missing recipient through the payroll UI. Delivery remains
  // queued because the isolated test environment keeps the mail worker off.
  const deliveryJob = jobs.find((job: { payroll_entry_id: string }) =>
    job.payroll_entry_id === preparedEntry.id,
  )
  expect(deliveryJob).toBeTruthy()
  await logout()
  await loginAsAdmin()
  await page.goto(`/payroll-runs/${draft.id}`)
  const deliveryCard = page.getByTestId(`delivery-${deliveryJob.id}`)
  await expect(deliveryCard).toContainText('Status: blocked email')
  const correctedEmail = `qa-finalized-${unique}@example.com`
  await deliveryCard.getByLabel('Correct recipient email').fill(correctedEmail)
  await deliveryCard.getByLabel('Action reason').fill('Verified address with fictional QA employee')
  const addressCorrection = page.waitForResponse(response =>
    response.url().includes(`/payroll/runs/${draft.id}/delivery/${deliveryJob.id}/address`) &&
    response.request().method() === 'POST',
  )
  await deliveryCard.getByRole('button', { name: 'Correct email and schedule' }).click()
  const addressCorrectionResponse = await addressCorrection
  expect(addressCorrectionResponse.status(), await addressCorrectionResponse.text()).toBe(200)
  await expect(deliveryCard).toContainText('Status: scheduled')
  const deliveryAfterAddressCorrection = await page.request.get(
    `${apiUrl}/payroll/runs/${draft.id}/delivery-status`,
    { headers: await bearer(page) },
  )
  expect(deliveryAfterAddressCorrection.status(), await deliveryAfterAddressCorrection.text()).toBe(200)
  const correctedJobs = await deliveryAfterAddressCorrection.json()
  expect(correctedJobs).toEqual(expect.arrayContaining([
    expect.objectContaining({
      id: deliveryJob.id,
      status: 'scheduled',
      recipient_snapshot: correctedEmail,
      last_action_reason: 'Verified address with fictional QA employee',
    }),
  ]))

  const payslip = await page.request.get(
    `${apiUrl}/payroll/runs/${draft.id}/entries/${preparedEntry.id}/payslip.pdf`,
    { headers: await bearer(page) },
  )
  expect(payslip.status()).toBe(200)
  expect(payslip.headers()['content-type']).toContain('application/pdf')
  const pdfBody = await payslip.body()
  expect(pdfBody.subarray(0, 5).toString()).toBe('%PDF-')

  finalizedPayrollCorrectionFixture = {
    employeeId: employee.id,
    employeeCode: employee.employee_code,
    groupId: group.id,
    runId: draft.id,
    entryId: preparedEntry.id,
    netPay: finalizedEntry.net_pay,
    unique,
  }
})

test('settles a finalized contribution through a later draft without changing the frozen payslip', async ({
  page,
  loginAsAdmin,
}) => {
  const fixture = finalizedPayrollCorrectionFixture
  expect(fixture, 'The prior payroll setup and finalization journey must pass first').toBeTruthy()
  if (!fixture) return
  await loginAsAdmin()

  // Import December attendance and prepare the later draft used to settle a
  // reasoned correction. The prior November payslip remains frozen.
  const decemberRows = ['employee_code,login_date,logout_date']
  for (let day = 1; day <= 15; day++) {
    const workDate = new Date(Date.UTC(2026, 11, day))
    if (workDate.getUTCDay() === 0 || workDate.getUTCDay() === 6) continue
    const date = workDate.toISOString().slice(0, 10)
    decemberRows.push(`${fixture.employeeCode},${date}T00:00:00Z,${date}T09:00:00Z`)
  }
  await page.goto('/daily-time-records')
  await page.getByTestId('import-dtr-csv-button').click()
  await page.getByPlaceholder(/employee_code/).fill(decemberRows.join('\n'))
  const decemberImport = page.waitForResponse(response =>
    response.url().includes('/daily-time-records/import-batches/commit') && response.request().method() === 'POST',
  )
  await page.getByTestId('csv-import-submit-button').click()
  const decemberImportResponse = await decemberImport
  expect(decemberImportResponse.status(), await decemberImportResponse.text()).toBe(200)
  await expect(page.getByText(`${decemberRows.length - 1} succeeded`)).toBeVisible()
  await page.getByTestId('csv-import-close-button').click()

  await page.goto('/payroll')
  await page.getByTestId('payroll-pay-group-select').click()
  await page.getByRole('option', { name: new RegExp(`QA semi-monthly ${fixture.unique}`) }).click()
  await page.getByTestId('payroll-period-from').fill('2026-12-01')
  await page.getByTestId('payroll-period-to').fill('2026-12-15')
  const decemberReadiness = page.waitForResponse(response =>
    response.url().includes('/payroll/runs/preflight') && response.request().method() === 'GET',
  )
  await page.getByTestId('payroll-preflight-button').click()
  expect((await decemberReadiness).status()).toBe(200)
  await expect(page.getByText('Ready for calculation review')).toBeVisible()
  const decemberPreparation = page.waitForResponse(response =>
    response.url().includes('/payroll/runs/prepare-attendance-draft') && response.request().method() === 'POST',
  )
  await page.getByTestId('payroll-prepare-draft-button').click()
  const decemberDraftResponse = await decemberPreparation
  expect(decemberDraftResponse.status(), await decemberDraftResponse.text()).toBe(201)
  const decemberDraft = await decemberDraftResponse.json()
  const decemberEntry = decemberDraft.entries.find(
    (entry: { employee_id: string }) => entry.employee_id === fixture.employeeId,
  )
  expect(decemberEntry).toBeTruthy()
  expect(decemberEntry.blockers, JSON.stringify(decemberEntry.blockers)).toEqual([])

  const novemberLedger = await page.request.get(
    `${apiUrl}/payroll/contribution-ledger?employee_code=${fixture.employeeCode}&contribution_month=2026-11-01&limit=100`,
    { headers: await bearer(page) },
  )
  expect(novemberLedger.status(), await novemberLedger.text()).toBe(200)
  const novemberRows = (await novemberLedger.json()).data
  const pagibigCollection = novemberRows.find(
    (row: { scheme: string; sequence: number }) => row.scheme === 'pagibig' && row.sequence === 0,
  )
  expect(pagibigCollection).toBeTruthy()

  await page.goto('/payroll')
  await page.getByTestId('payroll-ledger-month').fill('2026-11')
  await page.getByTestId('payroll-ledger-employee-code').fill(fixture.employeeCode)
  const decemberCorrectionRow = page
    .getByRole('region', { name: 'Monthly statutory contribution ledger' })
    .getByRole('row')
    .filter({ hasText: 'PAGIBIG' })
  await decemberCorrectionRow.getByRole('button', { name: 'Correct in later draft' }).click()
  const correctionTargets = page.waitForResponse(response =>
    response.url().includes(`/payroll/contribution-ledger/${pagibigCollection.id}/correction-targets`) && response.request().method() === 'GET',
  )
  expect((await correctionTargets).status()).toBe(200)
  await page.getByLabel('Later payroll draft').selectOption(decemberEntry.id)
  await page.getByLabel('Employee contribution change').fill('-10.00')
  await page.getByLabel('Employer contribution change').fill('0.00')
  await page.getByLabel('Reviewed BIR withholding change').fill('0.00')
  await page.getByLabel('BIR tax review reference (required for employee correction)').fill(
    'QA reviewed same-year BIR adjustment workpaper',
  )
  await page.getByLabel('Reason').fill('Correct documented November over-collection')
  await page.getByLabel('Reconciliation reference').fill('QA contribution reconciliation 2026-11')
  const correctionResponsePromise = page.waitForResponse(response =>
    response.url().includes('/payroll/contribution-ledger/corrections') && response.request().method() === 'POST',
  )
  await page.getByRole('button', { name: 'Apply to draft' }).click()
  const correctionResponse = await correctionResponsePromise
  expect(correctionResponse.status(), await correctionResponse.text()).toBe(201)
  await expect(decemberCorrectionRow.getByText('Correct documented November over-collection')).toBeVisible()

  const correctedDecember = await page.request.get(`${apiUrl}/payroll/runs/${decemberDraft.id}`, {
    headers: await bearer(page),
  })
  expect(correctedDecember.status(), await correctedDecember.text()).toBe(200)
  const correctedDecemberRun = await correctedDecember.json()
  const correctedDecemberEntry = correctedDecemberRun.entries.find(
    (entry: { id: string }) => entry.id === decemberEntry.id,
  )
  expect(correctedDecemberEntry.deductions.pagibig_correction).toBe('-10.00')
  expect(correctedDecemberEntry.net_pay).toBe((Number(decemberEntry.net_pay) + 10).toFixed(2))
  expect(correctedDecemberEntry.taxable_income).toBe((Number(decemberEntry.taxable_income) + 10).toFixed(2))
  const novemberReadback = await page.request.get(`${apiUrl}/payroll/runs/${fixture.runId}`, {
    headers: await bearer(page),
  })
  expect(novemberReadback.status(), await novemberReadback.text()).toBe(200)
  const unchangedNovember = (await novemberReadback.json()).entries.find(
    (entry: { id: string }) => entry.id === fixture.entryId,
  )
  expect(unchangedNovember.net_pay).toBe(fixture.netPay)
})
