import { test, expect } from '../fixtures'
import { createParent, waitForWrite, assertWrite } from '../helpers/crud-journey'
import { DailyTimeRecordsPage } from '../pages/daily-time-records.page'

test.describe('Daily Time Records E2E', () => {
  test.beforeEach(async ({ loginAsAdmin }) => {
    await loginAsAdmin()
  })

  test('should display the DTR list', async ({ page }) => {
    const dtr = new DailyTimeRecordsPage(page)
    await dtr.goto()
    const count = await dtr.getRowCount()
    expect(count).toBeGreaterThanOrEqual(0)
  })

  test('should retry on error', async ({ page }) => {
    const dtr = new DailyTimeRecordsPage(page)
    await dtr.goto()
    await page.route('**/api/v1/daily-time-records?**', route => route.fulfill({ status: 500, json: { error: { message: 'Injected test failure' } } }))
    await page.reload()
    await expect(page.getByText('Failed to load daily time records.')).toBeVisible({ timeout: 15000 })
    await page.unroute('**/api/v1/daily-time-records?**')
    await page.getByRole('button', { name: 'Try again', exact: true }).click()
    await expect(page.getByText('Failed to load daily time records.')).not.toBeVisible({ timeout: 10000 })
    await expect(page.locator('table')).toBeVisible()
  })
})

test('imports a punch through the UI then edits and deletes it', async ({ page, loginAsAdmin }) => {
 await loginAsAdmin()
 const unique = Date.now().toString(36)
 const employee = await createParent(page, 'employees', { employee_code: 'I' + unique, first_name: 'Import', last_name: unique, birthdate: '1990-01-01' })
 await page.goto('/daily-time-records')
 await page.getByTestId('import-dtr-csv-button').click()
 await page.getByPlaceholder(/employee_code/).fill('employee_code,login_date,logout_date\n' + employee.employee_code + ',2026-10-02T08:00:00Z,2026-10-02T17:00:00Z')
 const importing = waitForWrite(page, 'daily-time-records', 'POST')
 await page.getByRole('button', { name: 'Import 1 Records', exact: true }).click()
 const created = await assertWrite(await importing, 201)
 await expect(page.getByText('1 succeeded')).toBeVisible()
 await page.getByRole('dialog').getByRole('button', { name: 'Close', exact: true }).first().click()
 await page.getByTestId('edit-daily-time-record-button-' + created.id).click()
 await page.getByTestId('dtr-logout-input').fill('2026-10-02T16:30')
 const editing = waitForWrite(page, 'daily-time-records', 'PATCH', created.id)
 await page.getByTestId('dtr-update-button').click()
 const updated = await assertWrite(await editing, 200)
 expect(updated.logout_date).toContain('16:30:00')
 await expect(page.getByTestId('dtr-update-button')).not.toBeVisible()
 await page.getByTestId('delete-daily-time-record-button-' + created.id).click()
 const deleting = waitForWrite(page, 'daily-time-records', 'DELETE', created.id)
 await page.getByRole('alertdialog').getByRole('button', { name: 'Delete', exact: true }).click()
 await assertWrite(await deleting, 200)
 await expect(page.getByTestId('edit-daily-time-record-button-' + created.id)).toHaveCount(0)
})
