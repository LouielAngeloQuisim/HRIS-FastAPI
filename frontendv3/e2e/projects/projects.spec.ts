import { test, expect } from '../fixtures'
import { ProjectsPage } from '../pages/projects.page'

test.describe('Projects E2E', () => {
  test.beforeEach(async ({ loginAsAdmin }) => {
    await loginAsAdmin()
  })

  test('should display the projects list', async ({ page }) => {
    const projects = new ProjectsPage(page)
    await projects.goto()
    const count = await projects.getRowCount()
    expect(count).toBeGreaterThanOrEqual(0)
  })

  test('should create a new project', async ({ page }) => {
    const projects = new ProjectsPage(page)
    await projects.goto()
    await projects.clickAdd()
    await projects.fillCode('E2E-PROJ-001')
    await projects.fillName('E2E Test Project')
    await projects.fillDescription('Created by E2E test')
    await projects.selectSubdivision('E2E Test Subdivision')
    await projects.selectProjectType('E2E Test Project Type')
    await projects.submit()
    await expect(page.locator('[data-testid="project-submit-button"]')).toHaveText('Create', { timeout: 10000 })
  })

  test('should edit an existing project', async ({ page }) => {
    const projects = new ProjectsPage(page)
    await projects.goto()
    const rowCount = await projects.getRowCount()
    if (rowCount > 0) {
      await projects.clickEditOnRow(0)
      await projects.fillName('Updated E2E Project')
      await projects.submit()
      await expect(page.locator('text=/success|updated/i')).toBeVisible({ timeout: 5000 })
    }
  })

  test('should delete a project', async ({ page }) => {
    const projects = new ProjectsPage(page)
    await projects.goto()
    const rowCount = await projects.getRowCount()
    if (rowCount > 0) {
      await projects.clickDeleteOnRow(0)
      await projects.confirmDelete()
      await expect(page.locator('text=/success|deleted/i')).toBeVisible({ timeout: 5000 })
    }
  })
})
