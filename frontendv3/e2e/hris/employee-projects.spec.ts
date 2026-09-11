import { test, expect } from '../fixtures'
import { EmployeeProjectsPage } from '../pages/employee-projects.page'

test.describe('Employee Projects E2E', () => {
  test.beforeEach(async ({ loginAsAdmin }) => {
    await loginAsAdmin()
  })

  test('should display the employee projects list', async ({ page }) => {
    const employeeProjects = new EmployeeProjectsPage(page)
    await employeeProjects.goto()
    const count = await employeeProjects.getRowCount()
    expect(count).toBeGreaterThanOrEqual(0)
  })

  test('should create a new employee project', async ({ page }) => {
    const employeeProjects = new EmployeeProjectsPage(page)
    await employeeProjects.goto()
    await employeeProjects.clickAdd()
    await employeeProjects.selectEmployee('E2E Test Employee')
    await employeeProjects.selectProject('E2E Test Project')
    await employeeProjects.fillDate('2026-09-11')
    await employeeProjects.fillRenderedHours('8')
    await employeeProjects.fillTask('E2E Test Task')
    await employeeProjects.fillAssigned('true')
    await employeeProjects.submit()
    await expect(page.locator('[data-testid="employee-project-submit-button"]')).toHaveText('Create', { timeout: 10000 })
  })

  test('should edit an existing employee project', async ({ page }) => {
    const employeeProjects = new EmployeeProjectsPage(page)
    await employeeProjects.goto()
    const rowCount = await employeeProjects.getRowCount()
    if (rowCount > 0) {
      await employeeProjects.clickEditOnRow(0)
      await employeeProjects.fillRenderedHours('9')
      await employeeProjects.submit()
      await expect(page.locator('text=/success|updated/i')).toBeVisible({ timeout: 5000 })
    }
  })

  test('should delete an employee project', async ({ page }) => {
    const employeeProjects = new EmployeeProjectsPage(page)
    await employeeProjects.goto()
    const rowCount = await employeeProjects.getRowCount()
    if (rowCount > 0) {
      await employeeProjects.clickDeleteOnRow(0)
      await employeeProjects.confirmDelete()
      await expect(page.locator('text=/success|deleted/i')).toBeVisible({ timeout: 5000 })
    }
  })
})
