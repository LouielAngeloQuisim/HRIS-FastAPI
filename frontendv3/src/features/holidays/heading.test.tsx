import { type Mock, describe, expect, it, vi } from 'vitest'
vi.mock("./components/resource-form", () => ({ ResourceForm: () => null }))
vi.mock("./components/resource-delete-dialog", () => ({ ResourceDeleteDialog: () => null }))
vi.mock("@/lib/api/client", () => ({ api: { delete: vi.fn() } }))
import { render } from 'vitest-browser-react'
import { type useHolidayConfigs } from '@/lib/api/holidays'
import HolidaysPage from './index'

const { refetch } = vi.hoisted(() => ({ refetch: vi.fn() }))

vi.mock('@/context/permissions-provider', () => ({
  useCan: () => true,
}))

vi.mock('@/tanstack/react-router', () => ({
  getRouteApi: () => ({ useSearch: () => ({}), useNavigate: () => vi.fn() }),
}))

const { useHolidayConfigsMock } = vi.hoisted(() => ({ useHolidayConfigsMock: vi.fn() as Mock<(...args: Parameters<typeof useHolidayConfigs>) => unknown> }))
vi.mock('@/lib/api/holidays', () => ({
  useHolidayConfigs: (...args: Parameters<typeof useHolidayConfigs>) => useHolidayConfigsMock(...args),
}))

vi.mock('@/components/layout/header', () => ({
  Header: ({ children }: { children?: React.ReactNode }) => <header>{children}</header>,
}))
vi.mock('@/components/search', () => ({ Search: () => null }))
vi.mock('@/components/theme-switch', () => ({ ThemeSwitch: () => null }))
vi.mock('@/components/config-drawer', () => ({ ConfigDrawer: () => null }))
vi.mock('@/components/profile-dropdown', () => ({ ProfileDropdown: () => null }))

describe('HolidaysPage (header)', () => {
  it('renders the page heading', async () => {
    useHolidayConfigsMock.mockReturnValue({
      data: { data: [], count: 0 },
      isPending: false,
      isError: false,
      refetch,
    })

    const screen = await render(<HolidaysPage />)
    await expect.element(screen.getByRole('heading', { name: 'Holiday Configuration' })).toBeVisible()
  })
})
