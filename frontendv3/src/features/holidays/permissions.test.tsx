import { describe, expect, it, vi } from 'vitest'
vi.mock("./components/resource-form", () => ({ ResourceForm: () => null }))
vi.mock("./components/resource-delete-dialog", () => ({ ResourceDeleteDialog: () => null }))
vi.mock("@/lib/api/client", () => ({ api: { delete: vi.fn() } }))
import { render } from 'vitest-browser-react'
import HolidaysPage from './index'

describe('HolidaysPage (permissions)', () => {
  it('denies access when user lacks view permission', async () => {
    vi.mock('@/context/permissions-provider', () => ({
      useCan: () => false,
    }))

    const { useHolidayConfigsMock } = vi.hoisted(() => ({ useHolidayConfigsMock: vi.fn(() => ({ data: { data: [], count: 0 }, isPending: false, isError: false, refetch: vi.fn() })) }))
    vi.mock('@/lib/api/holidays', () => ({
      useHolidayConfigs: (...args: any[]) => (useHolidayConfigsMock as any)(...args),
    }))

    vi.mock('@/components/layout/header', () => ({
      Header: ({ children }: { children?: React.ReactNode }) => <header>{children}</header>,
    }))
    vi.mock('@/components/search', () => ({ Search: () => null }))
    vi.mock('@/components/theme-switch', () => ({ ThemeSwitch: () => null }))
    vi.mock('@/components/config-drawer', () => ({ ConfigDrawer: () => null }))
    vi.mock('@/components/profile-dropdown', () => ({ ProfileDropdown: () => null }))

    const screen = await render(<HolidaysPage />)
    await expect.element(screen.getByText('You do not have permission to view holiday configurations.')).toBeVisible()
  })
})
