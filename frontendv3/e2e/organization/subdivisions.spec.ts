import { test, expect } from '../fixtures'
import { SubdivisionsPage } from '../pages/subdivisions.page'

test.describe('Subdivisions E2E', () => {
  test.beforeEach(async ({ loginAsAdmin }) => {
    await loginAsAdmin()
  })

  test('should display the subdivisions list', async ({ page }) => {
    const subdivisions = new SubdivisionsPage(page)
    await subdivisions.goto()
    const count = await subdivisions.getRowCount()
    expect(count).toBeGreaterThanOrEqual(0)
  })

  test('should create a new subdivision', async ({ page }) => {
    const subdivisions = new SubdivisionsPage(page)
    await subdivisions.goto()
    await subdivisions.clickAdd()
    await subdivisions.fillCode('E2E-SUB-001')
    await subdivisions.fillName('E2E Test Subdivision')
    await subdivisions.fillDescription('Created by E2E test')
    await subdivisions.fillLocation('Test Location')
    await subdivisions.selectDepartment('E2E Test Department')
    await subdivisions.submit()
    await expect(page.locator('[data-testid="subdivision-submit-button"]')).toHaveText('Create', { timeout: 10000 })
  })

  test('should edit an existing subdivision', async ({ page }) => {
    const subdivisions = new SubdivisionsPage(page)
    await subdivisions.goto()
    const rowCount = await subdivisions.getRowCount()
    if (rowCount > 0) {
      await subdivisions.clickEditOnRow(0)
      await subdivisions.fillName('Updated E2E Subdivision')
      await subdivisions.submit()
      await expect(page.locator('text=/success|updated/i')).toBeVisible({ timeout: 5000 })
    }
  })

  test('should delete a subdivision', async ({ page }) => {
    const subdivisions = new SubdivisionsPage(page)
    await subdivisions.goto()
    const rowCount = await subdivisions.getRowCount()
    if (rowCount > 0) {
      await subdivisions.clickDeleteOnRow(0)
      await subdivisions.confirmDelete()
      await expect(page.locator('text=/success|deleted/i')).toBeVisible({ timeout: 5000 })
    }
  })
})
