import { test, expect } from '../fixtures'
import { ProjectTypesPage } from '../pages/project-types.page'

test.describe('Project Types E2E', () => {
  test.beforeEach(async ({ loginAsAdmin }) => {
    await loginAsAdmin()
  })

  test('should display the project types list', async ({ page }) => {
    const projectTypes = new ProjectTypesPage(page)
    await projectTypes.goto()
    const count = await projectTypes.getRowCount()
    expect(count).toBeGreaterThanOrEqual(0)
  })

  test('should create a new project type', async ({ page }) => {
    const projectTypes = new ProjectTypesPage(page)
    await projectTypes.goto()
    await projectTypes.clickAdd()
    await projectTypes.fillCode('E2E-PT-001')
    await projectTypes.fillName('E2E Test Project Type')
    await projectTypes.fillDescription('Created by E2E test')
    await projectTypes.submit()
    await expect(page.locator('[data-testid="project-type-submit-button"]')).toHaveText('Create', { timeout: 10000 })
  })

  test('should edit an existing project type', async ({ page }) => {
    const projectTypes = new ProjectTypesPage(page)
    await projectTypes.goto()
    const rowCount = await projectTypes.getRowCount()
    if (rowCount > 0) {
      await projectTypes.clickEditOnRow(0)
      await projectTypes.fillName('Updated E2E Project Type')
      await projectTypes.submit()
      await expect(page.locator('text=/success|updated/i')).toBeVisible({ timeout: 5000 })
    }
  })

  test('should delete a project type', async ({ page }) => {
    const projectTypes = new ProjectTypesPage(page)
    await projectTypes.goto()
    const rowCount = await projectTypes.getRowCount()
    if (rowCount > 0) {
      await projectTypes.clickDeleteOnRow(0)
      await projectTypes.confirmDelete()
      await expect(page.locator('text=/success|deleted/i')).toBeVisible({ timeout: 5000 })
    }
  })
})
