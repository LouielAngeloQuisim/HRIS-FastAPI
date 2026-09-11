import { type Page, type Locator, expect } from '@playwright/test'

export class DashboardPage {
  readonly page: Page
  readonly title: Locator
  readonly kpiEmployees: Locator
  readonly kpiDivisions: Locator
  readonly kpiDepartments: Locator
  readonly kpiProjects: Locator
  readonly kpiSubdivisions: Locator
  readonly kpiOwners: Locator
  readonly kpiEmployeeProjects: Locator
  readonly kpiModelCount: Locator
  readonly kpiDailyTimeRecords: Locator

  constructor(page: Page) {
    this.page = page
    this.title = page.locator('h1:has-text("Dashboard"), h2:has-text("Dashboard")')
    this.kpiEmployees = page.locator('[data-testid="kpi-employee_records"]')
    this.kpiDivisions = page.locator('[data-testid="kpi-divisions"]')
    this.kpiDepartments = page.locator('[data-testid="kpi-departments"]')
    this.kpiProjects = page.locator('[data-testid="kpi-projects"]')
    this.kpiSubdivisions = page.locator('[data-testid="kpi-subdivisions"]')
    this.kpiOwners = page.locator('[data-testid="kpi-owners"]')
    this.kpiEmployeeProjects = page.locator('[data-testid="kpi-employee_projects"]')
    this.kpiModelCount = page.locator('[data-testid="kpi-model_count"]')
    this.kpiDailyTimeRecords = page.locator('[data-testid="kpi-dtr_records_daily_count"]')
  }

  async goto() {
    await this.page.goto('/')
    await expect(this.title).toBeVisible({ timeout: 5000 })
  }

  async getKpiValue(key: 'employee_records' | 'divisions' | 'departments' | 'projects' | 'subdivisions' | 'owners' | 'employee_projects' | 'model_count' | 'dtr_records_daily_count'): Promise<string> {
    const locatorMap: Record<string, Locator> = {
      employee_records: this.kpiEmployees,
      divisions: this.kpiDivisions,
      departments: this.kpiDepartments,
      projects: this.kpiProjects,
      subdivisions: this.kpiSubdivisions,
      owners: this.kpiOwners,
      employee_projects: this.kpiEmployeeProjects,
      model_count: this.kpiModelCount,
      dtr_records_daily_count: this.kpiDailyTimeRecords,
    }
    return await locatorMap[key].textContent() ?? ''
  }
}
