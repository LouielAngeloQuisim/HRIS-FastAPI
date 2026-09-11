import { type Page, type APIRequestContext, expect } from '@playwright/test'

export interface AuthFixtures {
  loginAsAdmin: () => Promise<void>
  loginAsUser: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  apiRequest: APIRequestContext
}

export async function injectAuthFixtures(page: Page): Promise<AuthFixtures> {
  const apiRequest = page.request
  const BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:5173'
  const API_URL = process.env.E2E_API_URL || 'http://localhost:8000/api/v1'

  async function login(email: string, password: string) {
    await page.goto(`${BASE_URL}/sign-in`)
    await page.locator('[data-testid="login-email-input"]').fill(email)
    await page.locator('[data-testid="login-password-input"]').fill(password)
    await page.locator('[data-testid="login-submit-button"]').click()
    await expect(page).not.toHaveURL(new RegExp(`/sign-in$`, 'i'), { timeout: 10000 })
  }

  return {
    loginAsAdmin: () => login('lacquisim@gmail.com', 'password'),
    loginAsUser: (email, password) => login(email, password),
    logout: async () => {
      const refreshToken = (await page.context().cookies())
        .find(cookie => cookie.name === 'hris_rt')
      if (!refreshToken) {
        throw new Error('Cannot log out without a refresh token')
      }

      const response = await page.request.post(`${API_URL}/logout`, {
        data: {
          refresh_token: refreshToken.value,
          all_sessions: false,
        },
      })
      if (!response.ok()) {
        throw new Error(`Logout failed with status ${response.status()}`)
      }

      await page.context().clearCookies()
      await page.goto(`${BASE_URL}/sign-in`)
      await expect(page).toHaveURL(`${BASE_URL}/sign-in`, { timeout: 5000 })
    },
    apiRequest,
  }
}
