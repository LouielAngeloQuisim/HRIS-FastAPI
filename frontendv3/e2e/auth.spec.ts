import { test, expect } from './fixtures'

const BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:5173'
const API_URL = process.env.E2E_API_URL || 'http://localhost:8000/api/v1'

const TEST_ADMIN = {
  email: 'lacquisim@gmail.com',
  password: 'password',
}

const TEST_USER = {
  email: 'user@example.com',
  password: 'changethis',
}

test.describe('Authentication E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.context().clearCookies()
  })

  test('should display login page', async ({ page }) => {
    await page.goto(`${BASE_URL}/sign-in`)

    await expect(page.locator('[data-testid="login-email-input"]')).toBeVisible()
    await expect(page.locator('[data-testid="login-password-input"]')).toBeVisible()
    await expect(page.locator('[data-testid="login-submit-button"]')).toBeVisible()
  })

  test('should show error for invalid credentials', async ({ page }) => {
    await page.goto(`${BASE_URL}/sign-in`)

    await page.locator('[data-testid="login-email-input"]').fill('invalid@example.com')
    await page.locator('[data-testid="login-password-input"]').fill('wrongpassword')
    await page.locator('[data-testid="login-submit-button"]').click()

    await expect(page.getByText(/incorrect email or password/i)).toBeVisible({ timeout: 5000 })
  })

  test('should login successfully with valid credentials', async ({ loginAsAdmin, page }) => {
    await loginAsAdmin()

    await expect(page).toHaveURL(`${BASE_URL}/`, { timeout: 10000 })

    const cookies = await page.context().cookies()
    const accessToken = cookies.find(cookie => cookie.name === 'hris_at')
    const refreshToken = cookies.find(cookie => cookie.name === 'hris_rt')

    expect(accessToken).toBeDefined()
    expect(refreshToken).toBeDefined()
  })

  test('should access protected routes after login', async ({ loginAsAdmin, page }) => {
    await loginAsAdmin()

    for (const path of ['/employees', '/divisions', '/departments']) {
      await page.goto(`${BASE_URL}${path}`)
      await expect(page).toHaveURL(new RegExp(`${path}/?$`))
    }
  })

  test('should logout successfully', async ({ page }) => {
    await page.goto(`${BASE_URL}/sign-in`)
    await page.locator('[data-testid="login-email-input"]').fill(TEST_ADMIN.email)
    await page.locator('[data-testid="login-password-input"]').fill(TEST_ADMIN.password)
    await page.locator('[data-testid="login-submit-button"]').click()
    await expect(page).toHaveURL(`${BASE_URL}/`, { timeout: 10000 })

    const refreshToken = (await page.context().cookies())
      .find(cookie => cookie.name === 'hris_rt')
    expect(refreshToken).toBeDefined()

    const logoutResponse = await page.request.post(`${API_URL}/logout`, {
      data: {
        refresh_token: refreshToken?.value,
        all_sessions: false,
      },
    })
    expect(logoutResponse.ok()).toBe(true)

    await page.context().clearCookies()
    await page.goto(`${BASE_URL}/sign-in`)
    await expect(page).toHaveURL(`${BASE_URL}/sign-in`, { timeout: 5000 })

    const cookies = await page.context().cookies()
    expect(cookies.find(cookie => cookie.name === 'hris_at')).toBeUndefined()
    expect(cookies.find(cookie => cookie.name === 'hris_rt')).toBeUndefined()

    const refreshResponse = await page.request.post(`${API_URL}/login/refresh-token`, {
      data: { refresh_token: refreshToken?.value },
    })
    expect(refreshResponse.status()).toBe(401)
  })

  test('should refresh an expired access token through the frontend client', async ({ loginAsAdmin, page }) => {
    await loginAsAdmin()

    const cookiesBefore = await page.context().cookies()
    const accessTokenBefore = cookiesBefore.find(cookie => cookie.name === 'hris_at')
    expect(accessTokenBefore).toBeDefined()

    await page.context().addCookies([{
      name: 'hris_at',
      value: 'invalid-access-token',
      url: BASE_URL,
    }])

    await page.goto(`${BASE_URL}/employees`)
    await expect(page.getByRole('heading', { name: /employee/i })).toBeVisible({ timeout: 10000 })

    const cookiesAfter = await page.context().cookies()
    const accessTokenAfter = cookiesAfter.find(cookie => cookie.name === 'hris_at')
    expect(accessTokenAfter?.value).not.toBe('invalid-access-token')
    expect(accessTokenAfter?.value).not.toBe(accessTokenBefore?.value)
  })
})

test.describe('Permission-based Access Control E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.context().clearCookies()
  })

  test('should deny access to admin routes for regular users', async ({ loginAsUser, page }) => {
    await loginAsUser(TEST_USER.email, TEST_USER.password)

    await page.goto(`${BASE_URL}/roles`)

    await expect(page.getByText(/you do not have permission to view roles/i)).toBeVisible({ timeout: 5000 })
    await expect(page.locator('table, [role="table"]')).toHaveCount(0)
  })

  test('should allow access to admin routes for superusers', async ({ loginAsAdmin, page }) => {
    await loginAsAdmin()

    await page.goto(`${BASE_URL}/roles`)
    await expect(page.getByRole('heading', { name: 'Roles' })).toBeVisible({ timeout: 5000 })
    await expect(page.locator('table, [role="table"]').first()).toBeVisible({ timeout: 5000 })
  })
})
