/**
 * E2E Tests for Authentication Flows
 * Tests critical user journeys: login, token refresh, logout
 */

import { test, expect } from '@playwright/test'

const BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:5173'
const API_URL = process.env.E2E_API_URL || 'http://localhost:8000/api/v1'

// Test credentials (should be seeded in test DB)
const TEST_ADMIN = {
  email: 'admin@example.com',
  password: 'changethis',
}

const TEST_USER = {
  email: 'user@example.com',
  password: 'changethis',
}

test.describe('Authentication E2E Tests', () => {
  test.describe.configure({ mode: 'serial' })

  test.beforeEach(async ({ page }) => {
    // Clear cookies before each test
    await page.context().clearCookies()
  })

  test('should display login page', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`)
    
    // Check login form elements
    await expect(page.locator('input[type="email"]').first()).toBeVisible()
    await expect(page.locator('input[type="password"]').first()).toBeVisible()
    await expect(page.locator('button[type="submit"]').first()).toBeVisible()
  })

  test('should show error for invalid credentials', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`)
    
    // Fill in invalid credentials
    await page.locator('input[type="email"]').first().fill('invalid@example.com')
    await page.locator('input[type="password"]').first().fill('wrongpassword')
    await page.locator('button[type="submit"]').first().click()
    
    // Should show error message
    await expect(page.locator('text=/incorrect email or password/i')).toBeVisible({ timeout: 5000 })
  })

  test('should login successfully with valid credentials', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`)
    
    // Fill in valid credentials
    await page.locator('input[type="email"]').first().fill(TEST_ADMIN.email)
    await page.locator('input[type="password"]').first().fill(TEST_ADMIN.password)
    await page.locator('button[type="submit"]').first().click()
    
    // Should redirect to dashboard
    await expect(page).toHaveURL(/.*dashboard/, { timeout: 10000 })
    
    // Check that auth cookies are set
    const cookies = await page.context().cookies()
    const accessToken = cookies.find(c => c.name === 'hris_at')
    const refreshToken = cookies.find(c => c.name === 'hris_rt')
    
    expect(accessToken).toBeDefined()
    expect(refreshToken).toBeDefined()
    
    // Verify cookie security flags (in production)
    if (page.url().startsWith('https://')) {
      expect(accessToken?.secure).toBe(true)
      expect(accessToken?.sameSite).toBe('Strict')
      expect(refreshToken?.secure).toBe(true)
      expect(refreshToken?.sameSite).toBe('Strict')
    }
  })

  test('should access protected routes after login', async ({ page }) => {
    // Login first
    await page.goto(`${BASE_URL}/login`)
    await page.locator('input[type="email"]').first().fill(TEST_ADMIN.email)
    await page.locator('input[type="password"]').first().fill(TEST_ADMIN.password)
    await page.locator('button[type="submit"]').first().click()
    await expect(page).toHaveURL(/.*dashboard/, { timeout: 10000 })
    
    // Navigate to protected routes
    await page.goto(`${BASE_URL}/employees`)
    await expect(page).toHaveURL(/.*employees/)
    
    await page.goto(`${BASE_URL}/divisions`)
    await expect(page).toHaveURL(/.*divisions/)
    
    await page.goto(`${BASE_URL}/departments`)
    await expect(page).toHaveURL(/.*departments/)
  })

  test('should logout successfully', async ({ page }) => {
    // Login first
    await page.goto(`${BASE_URL}/login`)
    await page.locator('input[type="email"]').first().fill(TEST_ADMIN.email)
    await page.locator('input[type="password"]').first().fill(TEST_ADMIN.password)
    await page.locator('button[type="submit"]').first().click()
    await expect(page).toHaveURL(/.*dashboard/, { timeout: 10000 })
    
    // Find and click logout button (adjust selector as needed)
    const logoutButton = page.locator('button:has-text("logout"), a:has-text("logout"), [data-testid="logout"]')
    if (await logoutButton.count() > 0) {
      await logoutButton.first().click()
    } else {
      // Alternative: Call logout API directly
      await page.request.post(`${API_URL}/logout`, {
        headers: {
          'Content-Type': 'application/json',
        },
      })
    }
    
    // Should redirect to login
    await expect(page).toHaveURL(/.*login/, { timeout: 5000 })
    
    // Verify cookies are cleared
    const cookies = await page.context().cookies()
    const accessToken = cookies.find(c => c.name === 'hris_at')
    const refreshToken = cookies.find(c => c.name === 'hris_rt')
    
    expect(accessToken).toBeUndefined()
    expect(refreshToken).toBeUndefined()
  })

  test('should handle token refresh on 401', async ({ page }) => {
    // Login first
    await page.goto(`${BASE_URL}/login`)
    await page.locator('input[type="email"]').first().fill(TEST_ADMIN.email)
    await page.locator('input[type="password"]').first().fill(TEST_ADMIN.password)
    await page.locator('button[type="submit"]').first().click()
    await expect(page).toHaveURL(/.*dashboard/, { timeout: 10000 })
    
    // Get initial tokens
    const cookiesBefore = await page.context().cookies()
    const accessTokenBefore = cookiesBefore.find(c => c.name === 'hris_at')
    
    // Simulate token expiration by making a request that returns 401
    // The frontend should automatically refresh the token
    await page.evaluate(() => {
      // Force a 401 response to test refresh flow
      return fetch('/api/v1/users/me', {
        headers: {
          'Authorization': 'Bearer invalid_token',
        },
      }).catch(() => {
        // Expected to fail
      })
    })
    
    // Wait a moment for potential token refresh
    await page.waitForTimeout(1000)
    
    // Check if new token is different (refreshed)
    const cookiesAfter = await page.context().cookies()
    const accessTokenAfter = cookiesAfter.find(c => c.name === 'hris_at')
    
    // Token should either be refreshed or user should be redirected to login
    const tokenRefreshed = accessTokenAfter?.value !== accessTokenBefore?.value
    const redirectedToLogin = page.url().includes('login')
    
    expect(tokenRefreshed || redirectedToLogin).toBe(true)
  })
})

test.describe('Permission-based Access Control E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.context().clearCookies()
  })

  test('should deny access to admin routes for regular users', async ({ page }) => {
    // Login as regular user
    await page.goto(`${BASE_URL}/login`)
    await page.locator('input[type="email"]').first().fill(TEST_USER.email)
    await page.locator('input[type="password"]').first().fill(TEST_USER.password)
    await page.locator('button[type="submit"]').first().click()
    
    // Try to access admin-only route
    await page.goto(`${BASE_URL}/roles`)
    
    // Should show 403 or redirect
    const forbidden = await page.locator('text=/403|forbidden|access denied/i').count() > 0
    const redirected = page.url().includes('login') || page.url().includes('dashboard')
    
    expect(forbidden || redirected).toBe(true)
  })

  test('should allow access to admin routes for superusers', async ({ page }) => {
    // Login as admin
    await page.goto(`${BASE_URL}/login`)
    await page.locator('input[type="email"]').first().fill(TEST_ADMIN.email)
    await page.locator('input[type="password"]').first().fill(TEST_ADMIN.password)
    await page.locator('button[type="submit"]').first().click()
    await expect(page).toHaveURL(/.*dashboard/, { timeout: 10000 })
    
    // Access admin route
    await page.goto(`${BASE_URL}/roles`)
    await expect(page).toHaveURL(/.*roles/)
    
    // Should see role management interface
    await expect(page.locator('table, [role="table"]').first()).toBeVisible({ timeout: 5000 })
  })
})
