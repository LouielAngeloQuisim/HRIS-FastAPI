import { test, expect } from '../fixtures'
import { apiUrl, assertWrite, createParent, waitForWrite } from '../helpers/crud-journey'

async function authHeaders(page: import('@playwright/test').Page) {
  const token = (await page.context().cookies()).find(cookie => cookie.name === 'hris_at')?.value
  if (!token) throw new Error('Missing authenticated test session')
  return { Authorization: `Bearer ${token}` }
}

test.describe('Batch 1 employee, salary and leave workflows', () => {
  test.beforeEach(async ({ loginAsAdmin }) => { await loginAsAdmin() })

  test('creates, edits, archives an employee through the UI and confirms the record is gone', async ({ page }) => {
    await page.goto('/employees')
    const code = `E2E${Date.now().toString(36)}`
    await page.getByTestId('add-employee-button').click()
    await page.getByTestId('resource-form-employee-code-input').fill(code)
    await page.getByTestId('resource-form-first-name-input').fill('Batch')
    await page.getByTestId('resource-form-last-name-input').fill('Employee')
    await page.getByTestId('resource-form-birthdate-input').fill('1990-02-03')
    const creating = waitForWrite(page, 'employees', 'POST')
    await page.getByTestId('resource-form-submit-button').click()
    const employee = await assertWrite(await creating, 201)
    await expect(page.getByText(code, { exact: true })).toBeVisible()

    await page.getByTestId(`edit-employee-button-${employee.id}`).click()
    await page.getByTestId('resource-form-last-name-input').fill('EmployeeEdited')
    const updating = waitForWrite(page, 'employees', 'PATCH', employee.id)
    await page.getByTestId('resource-form-submit-button').click()
    await assertWrite(await updating, 200)
    await expect(page.getByRole('row').filter({ hasText: code }).getByRole('link', { name: 'EmployeeEdited, Batch', exact: true })).toBeVisible()

    await page.getByTestId(`archive-employee-button-${employee.id}`).click()
    await expect(page.getByRole('alertdialog')).toBeVisible()
    const deleting = waitForWrite(page, 'employees', 'DELETE', employee.id)
    await page.getByRole('button', { name: 'Delete', exact: true }).last().click()
    await assertWrite(await deleting, 200)
    await expect(page.getByTestId(`edit-employee-button-${employee.id}`)).toHaveCount(0)
    const archived = await page.request.get(`${apiUrl}/employees/${employee.id}`, { headers: await authHeaders(page) })
    expect(archived.status()).toBe(404)
  })

  test('sets up, edits and archives salary without deleting the employee', async ({ page }) => {
    const unique = Date.now().toString(36)
    const employee = await createParent(page, 'employees', { employee_code: `SAL${unique}`, first_name: 'Salary', last_name: 'Fixture', birthdate: '1990-01-01' })
    await page.goto('/payroll/salary')
    await page.getByTestId('salary-employee-select').click()
    await page.getByRole('option', { name: new RegExp(`SAL${unique}.*Salary Fixture`) }).click()
    await page.getByTestId('add-salary-button').click()
    await page.getByTestId('salary-form-basic-rate-input').fill('18000.00')
    await page.getByTestId('salary-form-effective-date-input').fill('2026-10-01')
    const creating = waitForWrite(page, `payroll/employees/${employee.id}/salary`, 'POST')
    await page.getByTestId('salary-form-submit-button').click()
    const salary = await assertWrite(await creating, 200)
    await expect(page.getByText('18000.00', { exact: true })).toBeVisible()
    await page.getByTestId(`edit-salary-button-${salary.id}`).press('Enter')
    await page.getByTestId('salary-form-basic-rate-input').fill('19000.00')
    const updating = waitForWrite(page, `payroll/salaries`, 'PATCH', salary.id)
    await page.getByTestId('salary-form-submit-button').click()
    await assertWrite(await updating, 200)
    const saved = await page.request.get(`${apiUrl}/payroll/employees/${employee.id}/salary`, { headers: await authHeaders(page) })
    expect(saved.status()).toBe(200)
    expect(await saved.json()).toEqual(expect.arrayContaining([expect.objectContaining({ id: salary.id, basic_rate: '19000.00' })]))

    await page.getByTestId(`edit-salary-button-${salary.id}`).press('Enter')
    await page.getByTestId('salary-form-archive-button').click()
    await expect(page.getByRole('alertdialog')).toBeVisible()
    const deleting = waitForWrite(page, 'payroll/salaries', 'DELETE', salary.id)
    await page.getByRole('button', { name: 'Delete', exact: true }).last().click()
    await assertWrite(await deleting, 200)
    const remainingSalaries = await page.request.get(`${apiUrl}/payroll/employees/${employee.id}/salary`, { headers: await authHeaders(page) })
    expect(await remainingSalaries.json()).toEqual([])
    expect((await page.request.get(`${apiUrl}/employees/${employee.id}`, { headers: await authHeaders(page) })).status()).toBe(200)
  })

  test('records and reloads reviewed tax-year inputs from the employee profile', async ({ page }) => {
    const unique = Date.now().toString(36)
    const employee = await createParent(page, 'employees', {
      employee_code: `TAX${unique}`,
      first_name: 'Tax',
      last_name: 'Review',
      birthdate: '1990-01-01',
    })
    const taxYear = new Date().getFullYear()
    const openingDate = new Date().toISOString().slice(0, 10)
    await page.goto(`/employees/${employee.id}`)
    await expect(page.getByText(/BIR tax-year inputs/)).toBeVisible()
    await page.getByLabel('Opening balances are complete through').fill(openingDate)
    await page.getByLabel('Taxable compensation already paid this year').fill('125000.00')
    await page.getByLabel('Withholding tax already withheld this year').fill('4500.00')
    await page.getByLabel('Figures include a previous employer').check()
    await page.getByLabel(/^Employee TIN$/i).fill('123-456-789-000')
    await page.getByLabel(/Employee RDO code/i).fill('039')
    await page.getByLabel(/^Registered address$/i).fill('1 Test Street')
    await page.getByLabel(/Registered address ZIP code/i).fill('1100')
    await page.getByLabel(/^Local home address$/i).fill('2 Home Street')
    await page.getByLabel(/Local home address ZIP code/i).fill('1100')
    await page.getByLabel(/Previous employer TIN/i).fill('987-654-321-000')
    await page.getByLabel(/Previous employer name/i).fill('Prior E2E Employer Inc.')
    await page.getByLabel(/Previous employer address$/i).fill('3 Business Street')
    await page.getByLabel(/Previous employer ZIP code/i).fill('1000')
    await page.getByLabel(/Previous employer period from/i).fill(`${taxYear}-01-01`)
    await page.getByLabel(/Previous employer period to/i).fill(`${taxYear}-03-31`)
    await page.getByLabel(/Identity supporting source/i).fill('Fictional E2E Form 2316 and identity documents')
    await page.getByLabel(/I checked the tax identity and address details/i).check()
    await page.getByLabel(/I reconciled 13th-month and other benefit payments/).check()
    await page.getByLabel(/Opening payroll periods covered by these totals/).fill('6')
    await page.getByLabel(/Source \/ review note/).fill('Form 2316 verified for test employee')
    await page.getByLabel(/I reviewed these figures/).check()

    const writing = waitForWrite(page, `payroll/employees/${employee.id}/tax-year-declarations`, 'PUT', String(taxYear))
    await page.getByRole('button', { name: 'Save tax-year inputs' }).click()
    const response = await assertWrite(await writing, 200)
    expect(response.is_verified).toBe(true)
    expect(response.taxable_compensation_ytd).toBe('125000.00')
    expect(response.tax_withheld_ytd).toBe('4500.00')
    expect(response.opening_as_of).toBe(openingDate)
    expect(response.certificate_identity_verified).toBe(true)
    expect(response.previous_employer_name).toBe('Prior E2E Employer Inc.')

    const readback = await page.request.get(
      `${apiUrl}/payroll/employees/${employee.id}/tax-year-declarations/${taxYear}`,
      { headers: await authHeaders(page) },
    )
    expect(readback.status()).toBe(200)
    expect(await readback.json()).toMatchObject({
      id: response.id,
      opening_pay_period_count: 6,
      opening_pay_period_type: 'monthly',
      employee_tin: '123-456-789-000',
      employee_rdo_code: '039',
      previous_employer_tin: '987-654-321-000',
      previous_employer_period_from: `${taxYear}-01-01`,
      certificate_identity_verified: true,
    })
    await page.reload()
    await expect(page.getByText(/Reviewed by payroll approver/)).toBeVisible()
    await expect(page.getByLabel('Taxable compensation already paid this year')).toHaveValue('125000.00')
  })

  test('recovers a missing salary through setup and keeps unverified payroll execution blocked', async ({ page }) => {
    const unique = Date.now().toString(36)
    const employee = await createParent(page, 'employees', {
      employee_code: `REC${unique}`,
      first_name: 'Payroll',
      last_name: 'Recovery',
      birthdate: '1990-01-01',
    })
    await page.goto('/payroll/salary')
    await page.getByLabel('Only employees without an effective salary').check()
    await page.getByTestId('salary-employee-select').click()
    await page.getByRole('option', { name: new RegExp(`REC${unique}.*Payroll Recovery`) }).click()
    await page.getByTestId('add-salary-button').click()
    await page.getByTestId('salary-form-basic-rate-input').fill('18000.00')
    await page.getByTestId('salary-form-effective-date-input').fill('2026-10-01')
    const salaryWrite = waitForWrite(page, `payroll/employees/${employee.id}/salary`, 'POST')
    await page.getByTestId('salary-form-submit-button').click()
    const salaryResponse = await assertWrite(await salaryWrite, 200)
    await expect(page.getByText('18000.00', { exact: true })).toBeVisible()

    const readback = await page.request.get(`${apiUrl}/payroll/employees/${employee.id}/salary`, { headers: await authHeaders(page) })
    expect(readback.status()).toBe(200)
    expect(await readback.json()).toEqual(expect.arrayContaining([expect.objectContaining({ id: salaryResponse.id, basic_rate: '18000.00' })]))

    await page.goto('/payroll')
    await expect(page.getByRole('heading', { name: 'Payroll readiness' })).toBeVisible()
    await expect(page.getByText(/statutory deductions.*remain disabled/i)).toBeVisible()
    const preview = await page.request.post(`${apiUrl}/payroll/runs/preview`, {
      headers: await authHeaders(page),
      data: { cutoff_type: 'monthly', date_from: '2026-10-01', date_to: '2026-10-31', employee_ids: [employee.id] },
    })
    expect(preview.status()).toBe(409)
    const generation = await page.request.post(`${apiUrl}/payroll/runs/generate`, {
      headers: await authHeaders(page),
      data: { cutoff_type: 'monthly', date_from: '2026-10-01', date_to: '2026-10-31', employee_ids: [employee.id], request_id: crypto.randomUUID() },
    })
    expect(generation.status()).toBe(409)
  })

  test('creates and archives a leave policy through the UI with API readback', async ({ page }) => {
    await page.goto('/leave-policies')
    const code = `LV${Date.now().toString(36)}`
    const name = `Batch One Leave ${code}`
    const updatedName = `${name} Updated`
    await page.getByTestId('add-leave-policy-button').click()
    await page.getByTestId('policy-form-code-input').fill(code)
    await page.getByTestId('policy-form-name-input').fill(name)
    await page.getByTestId('policy-form-entitlement-input').fill('12.00')
    const creating = waitForWrite(page, 'leave-policies', 'POST')
    await page.getByTestId('policy-form-submit-button').click()
    const policy = await assertWrite(await creating, 201)
    const policyRow = page.getByRole('row').filter({ hasText: code })
    await expect(policyRow.getByText(name, { exact: true })).toBeVisible()

    await page.getByTestId(`edit-leave-policy-button-${policy.id}`).click()
    await page.getByTestId('policy-form-name-input').fill(updatedName)
    const updating = waitForWrite(page, 'leave-policies', 'PATCH', policy.id)
    await page.getByTestId('policy-form-submit-button').click()
    await assertWrite(await updating, 200)
    await expect(policyRow.getByText(updatedName, { exact: true })).toBeVisible()

    await page.getByTestId(`archive-leave-policy-button-${policy.id}`).click()
    await expect(page.getByRole('alertdialog')).toBeVisible()
    const deleting = waitForWrite(page, 'leave-policies', 'DELETE', policy.id)
    await page.getByRole('button', { name: 'Delete', exact: true }).last().click()
    await assertWrite(await deleting, 200)
    expect((await page.request.get(`${apiUrl}/leave-policies/${policy.id}`, { headers: await authHeaders(page) })).status()).toBe(404)
  })

  test('enrolls an employee in a policy through the UI and reads the saved enrollment', async ({ page }) => {
    const unique = Date.now().toString(36)
    const employee = await createParent(page, 'employees', { employee_code: `ENR${unique}`, first_name: 'Enrollment', last_name: 'Fixture', birthdate: '1990-01-01' })
    const policy = await createParent(page, 'leave-policies', { code: `ENR${unique}`, name: 'Enrollment fixture policy', annual_entitlement_days: '12.00', cadence: 'annual' })
    await page.goto('/leave-enrollments')
    await page.getByTestId('enrollment-employee-select').click()
    await page.getByRole('option', { name: new RegExp(`ENR${unique}.*Enrollment Fixture`) }).click()
    await page.getByTestId('enroll-employee-button').click()
    await page.getByTestId('enrollment-dialog-policy-select').click()
    await page.getByRole('option', { name: new RegExp(`ENR${unique}.*Enrollment fixture policy`) }).click()
    const enrolling = waitForWrite(page, `employees/${employee.id}/leave-enrollments`, 'POST')
    await page.getByTestId('enrollment-dialog-submit-button').click()
    const enrollment = await assertWrite(await enrolling, 201)
    await expect(page.getByText('Enrollment fixture policy', { exact: true })).toBeVisible()
    const readback = await page.request.get(`${apiUrl}/employees/${employee.id}/leave-enrollments?leave_year=2026`, { headers: await authHeaders(page) })
    expect(readback.status()).toBe(200)
    expect(await readback.json()).toEqual(expect.objectContaining({ data: expect.arrayContaining([expect.objectContaining({ id: enrollment.id, policy_id: policy.id })]) }))
  })
})
