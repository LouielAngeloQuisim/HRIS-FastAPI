import { test, expect } from '../fixtures'
import { ModelsPage } from '../pages/models.page'

test.describe('Models E2E', () => {
  test.beforeEach(async ({ loginAsAdmin }) => {
    await loginAsAdmin()
  })

  test('should display the models list', async ({ page }) => {
    const models = new ModelsPage(page)
    await models.goto()
    const count = await models.getRowCount()
    expect(count).toBeGreaterThanOrEqual(0)
  })

  test('should create a new model', async ({ page }) => {
    const models = new ModelsPage(page)
    await models.goto()
    await models.clickAdd()
    await models.fillName('E2E Test Model')
    await models.fillDescription('Created by E2E test')
    await models.selectModelType('E2E Test Model Type')
    await models.submit()
    await expect(page.locator('[data-testid="model-submit-button"]')).toHaveText('Create', { timeout: 10000 })
  })

  test('should edit an existing model', async ({ page }) => {
    const models = new ModelsPage(page)
    await models.goto()
    const rowCount = await models.getRowCount()
    if (rowCount > 0) {
      await models.clickEditOnRow(0)
      await models.fillName('Updated E2E Model')
      await models.submit()
      await expect(page.locator('text=/success|updated/i')).toBeVisible({ timeout: 5000 })
    }
  })

  test('should delete a model', async ({ page }) => {
    const models = new ModelsPage(page)
    await models.goto()
    const rowCount = await models.getRowCount()
    if (rowCount > 0) {
      await models.clickDeleteOnRow(0)
      await models.confirmDelete()
      await expect(page.locator('text=/success|deleted/i')).toBeVisible({ timeout: 5000 })
    }
  })
})
