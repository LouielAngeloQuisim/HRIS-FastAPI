import { test, expect } from '../fixtures'
import { apiUrl, assertWrite, createParent, waitForWrite } from '../helpers/crud-journey'
import { PayrollExecutionPage } from '../pages/payroll-execution.page'

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
    await expect(page.getByText('EmployeeEdited', { exact: true })).toBeVisible()

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

    await page.getByTestId(`edit-salary-button-${salary.id}`).click()
    await page.getByTestId('salary-form-basic-rate-input').fill('19000.00')
    const updating = waitForWrite(page, `payroll/salaries`, 'PATCH', salary.id)
    await page.getByTestId('salary-form-submit-button').click()
    await assertWrite(await updating, 200)
    const saved = await page.request.get(`${apiUrl}/payroll/employees/${employee.id}/salary`, { headers: await authHeaders(page) })
    expect(saved.status()).toBe(200)
    expect(await saved.json()).toEqual(expect.arrayContaining([expect.objectContaining({ id: salary.id, basic_rate: '19000.00' })]))

    await page.getByTestId(`edit-salary-button-${salary.id}`).click()
    await page.getByTestId('salary-form-archive-button').click()
    await expect(page.getByRole('alertdialog')).toBeVisible()
    const deleting = waitForWrite(page, 'payroll/salaries', 'DELETE', salary.id)
    await page.getByRole('button', { name: 'Delete', exact: true }).last().click()
    await assertWrite(await deleting, 200)
    const remainingSalaries = await page.request.get(`${apiUrl}/payroll/employees/${employee.id}/salary`, { headers: await authHeaders(page) })
    expect(await remainingSalaries.json()).toEqual([])
    expect((await page.request.get(`${apiUrl}/employees/${employee.id}`, { headers: await authHeaders(page) })).status()).toBe(200)
  })

  test('recovers a missing salary through setup, then reviews and generates payroll', async ({ page }) => {
    const unique = Date.now().toString(36)
    const employee = await createParent(page, 'employees', {
      employee_code: `REC${unique}`,
      first_name: 'Payroll',
      last_name: 'Recovery',
      birthdate: '1990-01-01',
    })
    const payroll = new PayrollExecutionPage(page)

    await payroll.openExecution()
    await payroll.selectEmployee('employee-filter-select', new RegExp(`REC${unique}.*Payroll Recovery`))
    const failedPreview = page.waitForResponse((response) =>
      response.request().method() === 'POST' && new URL(response.url()).pathname.endsWith('/payroll/runs/preview'),
    )
    await payroll.previewPeriod('2026-10-01', '2026-10-31')
    expect((await failedPreview).status()).toBe(422)
    await expect(page.getByTestId('missing-salary-recovery')).toBeVisible()

    await payroll.openSalaryRecovery()
    await payroll.selectEmployee('salary-employee-select', new RegExp(`REC${unique}.*Payroll Recovery`))
    const salaryResponse = await payroll.createSalary('18000.00', '2026-10-01')
    expect(salaryResponse.status()).toBe(200)
    await expect(page.getByText('18000.00', { exact: true })).toBeVisible()

    await payroll.openExecution()
    await payroll.selectEmployee('employee-filter-select', new RegExp(`REC${unique}.*Payroll Recovery`))
    const preview = page.waitForResponse((response) =>
      response.request().method() === 'POST' && new URL(response.url()).pathname.endsWith('/payroll/runs/preview'),
    )
    await payroll.previewPeriod('2026-10-01', '2026-10-31')
    const previewResponse = await preview
    expect(previewResponse.status()).toBe(200)
    expect((await previewResponse.json()).entries).toEqual(expect.arrayContaining([expect.objectContaining({ employee_id: employee.id, basic_rate: '18000.00' })]))

    const generation = page.waitForResponse((response) =>
      response.request().method() === 'POST' && new URL(response.url()).pathname.endsWith('/payroll/runs/generate'),
    )
    await payroll.generateReviewedPayroll()
    const generatedResponse = await generation
    expect(generatedResponse.status()).toBe(200)
    const run = await generatedResponse.json()
    const readback = await page.request.get(`${apiUrl}/payroll/runs/${run.id}`, { headers: await authHeaders(page) })
    expect(readback.status()).toBe(200)
    expect(await readback.json()).toEqual(expect.objectContaining({
      id: run.id,
      status: 'draft',
      entries: expect.arrayContaining([expect.objectContaining({ employee_id: employee.id, basic_rate: '18000.00' })]),
    }))
  })

  test('creates and archives a leave policy through the UI with API readback', async ({ page }) => {
    await page.goto('/leave-policies')
    const code = `LV${Date.now().toString(36)}`
    await page.getByTestId('add-leave-policy-button').click()
    await page.getByTestId('policy-form-code-input').fill(code)
    await page.getByTestId('policy-form-name-input').fill('Batch One Leave')
    await page.getByTestId('policy-form-entitlement-input').fill('12.00')
    const creating = waitForWrite(page, 'leave-policies', 'POST')
    await page.getByTestId('policy-form-submit-button').click()
    const policy = await assertWrite(await creating, 201)
    await expect(page.getByText('Batch One Leave', { exact: true })).toBeVisible()

    await page.getByTestId(`edit-leave-policy-button-${policy.id}`).click()
    await page.getByTestId('policy-form-name-input').fill('Batch One Leave Updated')
    const updating = waitForWrite(page, 'leave-policies', 'PATCH', policy.id)
    await page.getByTestId('policy-form-submit-button').click()
    await assertWrite(await updating, 200)
    await expect(page.getByText('Batch One Leave Updated', { exact: true })).toBeVisible()

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
