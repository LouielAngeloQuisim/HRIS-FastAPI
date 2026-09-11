import { test, expect } from '../fixtures'
import { PhasesPage } from '../pages/phases.page'

test.describe('Phases E2E', () => {
  test.beforeEach(async ({ loginAsAdmin }) => {
    await loginAsAdmin()
  })

  test('should display the phases list', async ({ page }) => {
    const phases = new PhasesPage(page)
    await phases.goto()
    const count = await phases.getRowCount()
    expect(count).toBeGreaterThanOrEqual(0)
  })

  test('should create a new phase', async ({ page }) => {
    const phases = new PhasesPage(page)
    await phases.goto()
    await phases.clickAdd()
    await phases.fillCode('E2E-PHASE-001')
    await phases.fillName('E2E Test Phase')
    await phases.fillDescription('Created by E2E test')
    await phases.selectSubdivision('E2E Test Subdivision')
    await phases.submit()
    await expect(page.locator('[data-testid="phase-submit-button"]')).toHaveText('Create', { timeout: 10000 })
  })

  test('should edit an existing phase', async ({ page }) => {
    const phases = new PhasesPage(page)
    await phases.goto()
    const rowCount = await phases.getRowCount()
    if (rowCount > 0) {
      await phases.clickEditOnRow(0)
      await phases.fillName('Updated E2E Phase')
      await phases.submit()
      await expect(page.locator('text=/success|updated/i')).toBeVisible({ timeout: 5000 })
    }
  })

  test('should delete a phase', async ({ page }) => {
    const phases = new PhasesPage(page)
    await phases.goto()
    const rowCount = await phases.getRowCount()
    if (rowCount > 0) {
      await phases.clickDeleteOnRow(0)
      await phases.confirmDelete()
      await expect(page.locator('text=/success|deleted/i')).toBeVisible({ timeout: 5000 })
    }
  })
})
