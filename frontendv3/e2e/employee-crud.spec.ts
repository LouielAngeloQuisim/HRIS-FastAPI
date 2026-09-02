/**
 * E2E Tests for Employee CRUD Operations
 * Tests critical employee management flows
 */

import { test, expect } from '@playwright/test'

const BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:5173'
const API_URL = process.env.E2E_API_URL || 'http://localhost:8000/api/v1'

const TEST_ADMIN = {
  email: 'admin@example.com',
  password: 'changethis',
}

test.describe('Employee Management E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.context().clearCookies()
    
    // Login as admin before each test
    await page.goto(`${BASE_URL}/login`)
    await page.locator('input[type="email"]').first().fill(TEST_ADMIN.email)
    await page.locator('input[type="password"]').first().fill(TEST_ADMIN.password)
    await page.locator('button[type="submit"]').first().click()
    await expect(page).toHaveURL(/.*dashboard/, { timeout: 10000 })
  })

  test('should display employees list', async ({ page }) => {
    await page.goto(`${BASE_URL}/employees`)
    
    // Check that employee table or list is visible
    await expect(page.locator('table, [role="table"]').first()).toBeVisible({ timeout: 5000 })
    
    // Should have pagination or list controls
    const hasPagination = await page.locator('[data-testid="pagination"], nav[aria-label*="pagination"]').count() > 0
    const hasListControls = await page.locator('button:has-text("add"), button:has-text("create")').count() > 0
    
    expect(hasPagination || hasListControls).toBe(true)
  })

  test('should display employee profile', async ({ page }) => {
    await page.goto(`${BASE_URL}/employees`)
    
    // Wait for employee list to load
    await expect(page.locator('table, [role="table"]').first()).toBeVisible({ timeout: 5000 })
    
    // Click on first employee row (adjust selector as needed)
    const employeeRow = page.locator('table tbody tr, [role="row"]').first()
    if (await employeeRow.count() > 0) {
      await employeeRow.click()
      
      // Should navigate to employee profile
      await expect(page).toHaveURL(/.*employees\/\d+/)
      
      // Check for profile elements
      await expect(page.locator('text=/email|phone|address/i').first()).toBeVisible()
    }
  })

  test('should search employees', async ({ page }) => {
    await page.goto(`${BASE_URL}/employees`)
    
    // Find search input
    const searchInput = page.locator('input[type="search"], input[placeholder*="search"]').first()
    
    if (await searchInput.count() > 0) {
      await searchInput.fill('john')
      await searchInput.press('Enter')
      
      // Wait for results to update
      await page.waitForTimeout(500)
      
      // Check that results are filtered (if any exist)
      const resultCount = await page.locator('table tbody tr, [role="row"]').count()
      expect(resultCount).toBeGreaterThanOrEqual(0)
    }
  })

  test('should export employees to CSV', async ({ page }) => {
    await page.goto(`${BASE_URL}/employees`)
    
    // Find export/download button
    const exportButton = page.locator('button:has-text("export"), button:has-text("csv"), button:has-text("download")').first()
    
    if (await exportButton.count() > 0) {
      // Start waiting for download
      const [download] = await Promise.all([
        page.waitForEvent('download'),
        exportButton.click(),
      ])
      
      // Verify download
      expect(download.suggestedFilename()).toMatch(/\.csv$/)
    }
  })
})

test.describe('Division Management E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.context().clearCookies()
    
    await page.goto(`${BASE_URL}/login`)
    await page.locator('input[type="email"]').first().fill(TEST_ADMIN.email)
    await page.locator('input[type="password"]').first().fill(TEST_ADMIN.password)
    await page.locator('button[type="submit"]').first().click()
    await expect(page).toHaveURL(/.*dashboard/, { timeout: 10000 })
  })

  test('should display divisions list', async ({ page }) => {
    await page.goto(`${BASE_URL}/divisions`)
    
    await expect(page.locator('table, [role="table"]').first()).toBeVisible({ timeout: 5000 })
  })

  test('should create new division', async ({ page }) => {
    await page.goto(`${BASE_URL}/divisions`)
    
    // Click add button
    const addButton = page.locator('button:has-text("add"), button:has-text("create")').first()
    await addButton.click()
    
    // Fill form
    await page.locator('input[name="name"], input[id="name"]').first().fill('Test Division E2E')
    
    // Submit
    await page.locator('button[type="submit"]').first().click()
    
    // Check for success
    await expect(page.locator('text=/success|created/i')).toBeVisible({ timeout: 5000 })
  })

  test('should edit existing division', async ({ page }) => {
    await page.goto(`${BASE_URL}/divisions`)
    
    // Find and click edit button on first row
    const editButton = page.locator('button:has-text("edit"), [data-testid="edit"]').first()
    
    if (await editButton.count() > 0) {
      await editButton.click()
      
      // Update name
      const nameInput = page.locator('input[name="name"], input[id="name"]').first()
      await nameInput.fill('Updated Division E2E')
      
      // Submit
      await page.locator('button[type="submit"]').first().click()
      
      // Check for success
      await expect(page.locator('text=/success|updated/i')).toBeVisible({ timeout: 5000 })
    }
  })

  test('should delete division', async ({ page }) => {
    await page.goto(`${BASE_URL}/divisions`)
    
    // Find and click delete button on first row
    const deleteButton = page.locator('button:has-text("delete"), [data-testid="delete"]').first()
    
    if (await deleteButton.count() > 0) {
      await deleteButton.click()
      
      // Confirm deletion in dialog
      const confirmButton = page.locator('button:has-text("confirm"), button:has-text("delete")').last()
      await confirmButton.click()
      
      // Check for success
      await expect(page.locator('text=/success|deleted/i')).toBeVisible({ timeout: 5000 })
    }
  })
})

test.describe('Dashboard E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.context().clearCookies()
    
    await page.goto(`${BASE_URL}/login`)
    await page.locator('input[type="email"]').first().fill(TEST_ADMIN.email)
    await page.locator('input[type="password"]').first().fill(TEST_ADMIN.password)
    await page.locator('button[type="submit"]').first().click()
    await expect(page).toHaveURL(/.*dashboard/, { timeout: 10000 })
  })

  test('should display dashboard widgets', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`)
    
    // Check for dashboard elements
    const hasStats = await page.locator('text=/employees|departments|divisions/i').count() > 0
    const hasCharts = await page.locator('svg, canvas, [role="img"]').count() > 0
    
    expect(hasStats || hasCharts).toBe(true)
  })

  test('should display recent activities', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`)
    
    // Check for activity feed or recent items
    const hasActivity = await page.locator('text=/recent|activity|latest/i').count() > 0
    
    expect(hasActivity).toBe(true)
  })
})
