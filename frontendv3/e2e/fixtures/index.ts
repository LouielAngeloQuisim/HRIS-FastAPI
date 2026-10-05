import { test as base } from '@playwright/test'
import { injectAuthFixtures } from './auth.fixture'

export const test = base.extend<{
  loginAsAdmin: () => Promise<void>
  loginAsUser: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
}>({
  loginAsAdmin: async ({ page }, use) => {
    const fixtures = await injectAuthFixtures(page)
    await use(fixtures.loginAsAdmin)
  },
  loginAsUser: async ({ page }, use) => {
    const fixtures = await injectAuthFixtures(page)
    await use(fixtures.loginAsUser)
  },
  logout: async ({ page }, use) => {
    const fixtures = await injectAuthFixtures(page)
    await use(fixtures.logout)
  },
})

export { expect } from '@playwright/test'
