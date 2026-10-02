import { test, expect } from '../fixtures'
test('mobile module pages can open navigation and reach project types', async ({ page, loginAsAdmin }) => {
 await loginAsAdmin()
 await page.setViewportSize({ width: 390, height: 844 })
 await page.goto('/projects')
 await page.getByTestId('mobile-sidebar-toggle').click()
 await expect(page.getByRole('link', { name: 'Project Types', exact: true })).toBeVisible()
 await page.getByRole('link', { name: 'Project Types', exact: true }).click()
 await expect(page.getByRole('heading', { name: 'Project Types', exact: true })).toBeVisible()
})
