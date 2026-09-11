import { test, expect } from '../fixtures'
import { DashboardPage } from '../pages/dashboard.page'

test.describe('Dashboard E2E', () => {
  test.beforeEach(async ({ loginAsAdmin }) => {
    await loginAsAdmin()
  })

  test('should display the dashboard with KPIs', async ({ page }) => {
    const dashboard = new DashboardPage(page)
    await dashboard.goto()
    await expect(dashboard.title).toBeVisible({ timeout: 5000 })
    const employeeCount = await dashboard.getKpiValue('employee_records')
    expect(employeeCount).toBeTruthy()
  })

  test('should display divisions KPI', async ({ page }) => {
    const dashboard = new DashboardPage(page)
    await dashboard.goto()
    const divisionsCount = await dashboard.getKpiValue('divisions')
    expect(divisionsCount).toBeTruthy()
  })

  test('should display projects KPI', async ({ page }) => {
    const dashboard = new DashboardPage(page)
    await dashboard.goto()
    const projectsCount = await dashboard.getKpiValue('projects')
    expect(projectsCount).toBeTruthy()
  })
})
