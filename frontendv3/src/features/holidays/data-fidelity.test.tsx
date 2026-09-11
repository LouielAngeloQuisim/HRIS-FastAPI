import { describe, expect, it, vi } from 'vitest'
vi.mock("./components/resource-form", () => ({ ResourceForm: () => null }))
vi.mock("./components/resource-delete-dialog", () => ({ ResourceDeleteDialog: () => null }))
vi.mock("@/lib/api/client", () => ({ api: { delete: vi.fn() } }))
import { render } from 'vitest-browser-react'
import HolidaysPage from './index'

const { refetch } = vi.hoisted(() => ({ refetch: vi.fn() }))

vi.mock('@/context/permissions-provider', () => ({
  useCan: () => true,
}))

vi.mock('@/tanstack/react-router', () => ({
  getRouteApi: () => ({ useSearch: () => ({}), useNavigate: () => vi.fn() }),
}))

const { useHolidayConfigsMock } = vi.hoisted(() => ({ useHolidayConfigsMock: vi.fn() }))
vi.mock('@/lib/api/holidays', () => ({
  useHolidayConfigs: (...args: unknown[]) => useHolidayConfigsMock(...args),
}))

vi.mock('@/components/layout/header', () => ({
  Header: ({ children }: { children?: React.ReactNode }) => <header>{children}</header>,
}))
vi.mock('@/components/search', () => ({ Search: () => null }))
vi.mock('@/components/theme-switch', () => ({ ThemeSwitch: () => null }))
vi.mock('@/components/config-drawer', () => ({ ConfigDrawer: () => null }))
vi.mock('@/components/profile-dropdown', () => ({ ProfileDropdown: () => null }))

describe('HolidaysPage (data fidelity)', () => {
  it('renders holiday config rows unmodified', async () => {
    useHolidayConfigsMock.mockReturnValue({
      data: {
        data: [
          {
            id: '1',
            code: 'NEWYEAR',
            name: "New Year's Day",
            month_day: '01-01',
            type: 'regular',
            region_code: null,
            is_recurring: true,
            is_active: true,
          },
          {
            id: '2',
            code: 'CHRISTMAS',
            name: 'Christmas Day',
            month_day: '12-25',
            type: 'regular',
            region_code: null,
            is_recurring: true,
            is_active: true,
          },
        ],
        count: 2,
      },
      isPending: false,
      isError: false,
      refetch,
    })

    const screen = await render(<HolidaysPage />)
    await expect.element(screen.getByText("New Year's Day")).toBeVisible()
    await expect.element(screen.getByText('Christmas Day')).toBeVisible()
    await expect.element(screen.getByText('01-01')).toBeVisible()
    await expect.element(screen.getByText('12-25')).toBeVisible()
  })
})
