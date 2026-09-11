import { test as base } from '@playwright/test'
import { injectAuthFixtures } from './auth.fixture'
import { seedTestData, cleanupTestData } from './api.fixture'
import type { TestDataIds } from './api.fixture'

export const test = base.extend<{
  loginAsAdmin: () => Promise<void>
  loginAsUser: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  seedData: () => Promise<TestDataIds>
  cleanupData: (ids: TestDataIds) => Promise<void>
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
  seedData: async ({ page }, use) => {
    const apiRequest = page.request
    const seed = async () => seedTestData(apiRequest)
    await use(seed)
  },
  cleanupData: async ({ page }, use) => {
    const apiRequest = page.request
    const cleanup = async (ids: TestDataIds) => cleanupTestData(apiRequest, ids)
    await use(cleanup)
  },
})

export { expect } from '@playwright/test'
