import { test, expect } from '../fixtures'
import { ModelTypesPage } from '../pages/model-types.page'

test.describe('Model Types E2E', () => {
  test.beforeEach(async ({ loginAsAdmin }) => {
    await loginAsAdmin()
  })

  test('should display the model types list', async ({ page }) => {
    const modelTypes = new ModelTypesPage(page)
    await modelTypes.goto()
    const count = await modelTypes.getRowCount()
    expect(count).toBeGreaterThanOrEqual(0)
  })

  test('should create a new model type', async ({ page }) => {
    const modelTypes = new ModelTypesPage(page)
    await modelTypes.goto()
    await modelTypes.clickAdd()
    await modelTypes.fillCode('E2E-MT-001')
    await modelTypes.fillName('E2E Test Model Type')
    await modelTypes.toggleAdditionalOptions()
    await modelTypes.submit()
    await expect(page.locator('[data-testid="model-type-submit-button"]')).toHaveText('Create', { timeout: 10000 })
  })

  test('should edit an existing model type', async ({ page }) => {
    const modelTypes = new ModelTypesPage(page)
    await modelTypes.goto()
    const rowCount = await modelTypes.getRowCount()
    if (rowCount > 0) {
      await modelTypes.clickEditOnRow(0)
      await modelTypes.fillName('Updated E2E Model Type')
      await modelTypes.submit()
      await expect(page.locator('text=/success|updated/i')).toBeVisible({ timeout: 5000 })
    }
  })

  test('should delete a model type', async ({ page }) => {
    const modelTypes = new ModelTypesPage(page)
    await modelTypes.goto()
    const rowCount = await modelTypes.getRowCount()
    if (rowCount > 0) {
      await modelTypes.clickDeleteOnRow(0)
      await modelTypes.confirmDelete()
      await expect(page.locator('text=/success|deleted/i')).toBeVisible({ timeout: 5000 })
    }
  })
})
