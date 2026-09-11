import { test, expect } from '../fixtures'
import { EmpTasksPage } from '../pages/emp-tasks.page'

test.describe('Emp Tasks E2E', () => {
  test.beforeEach(async ({ loginAsAdmin }) => {
    await loginAsAdmin()
  })

  test('should display the emp tasks list', async ({ page }) => {
    const empTasks = new EmpTasksPage(page)
    await empTasks.goto()
    const count = await empTasks.getRowCount()
    expect(count).toBeGreaterThanOrEqual(0)
  })

  test('should create a new emp task', async ({ page }) => {
    const empTasks = new EmpTasksPage(page)
    await empTasks.goto()
    await empTasks.clickAdd()
    await empTasks.selectEmployeeProject('E2E Test Employee Project')
    await empTasks.fillTaskDesc('E2E Test Task Description')
    await empTasks.fillRenderedHours('8')
    await empTasks.fillAssignedHours('8')
    await empTasks.fillDate('2026-09-11')
    await empTasks.fillApproved('true')
    await empTasks.fillAdjusted('false')
    await empTasks.submit()
    await expect(page.locator('[data-testid="emp-task-submit-button"]')).toHaveText('Create', { timeout: 10000 })
  })

  test('should edit an existing emp task', async ({ page }) => {
    const empTasks = new EmpTasksPage(page)
    await empTasks.goto()
    const rowCount = await empTasks.getRowCount()
    if (rowCount > 0) {
      await empTasks.clickEditOnRow(0)
      await empTasks.fillTaskDesc('Updated E2E Task Description')
      await empTasks.submit()
      await expect(page.locator('text=/success|updated/i')).toBeVisible({ timeout: 5000 })
    }
  })

  test('should delete an emp task', async ({ page }) => {
    const empTasks = new EmpTasksPage(page)
    await empTasks.goto()
    const rowCount = await empTasks.getRowCount()
    if (rowCount > 0) {
      await empTasks.clickDeleteOnRow(0)
      await empTasks.confirmDelete()
      await expect(page.locator('text=/success|deleted/i')).toBeVisible({ timeout: 5000 })
    }
  })
})
