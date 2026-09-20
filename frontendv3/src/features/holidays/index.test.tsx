import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import HolidaysPage from './index'

vi.mock('./components/resource-form', () => ({
  ResourceForm: () => null,
}))
vi.mock('./components/resource-delete-dialog', () => ({
  ResourceDeleteDialog: () => null,
}))

const { useHolidayConfigsMock } = vi.hoisted(() => ({
  useHolidayConfigsMock: vi.fn()
}))
vi.mock('@/lib/api/holidays', () => ({
  useHolidayConfigs: () => useHolidayConfigsMock(),
}))

vi.mock('@/components/layout/header', () => ({
  Header: ({ children }: { children?: React.ReactNode }) => <header>{children}</header>,
}))
vi.mock('@/components/search', () => ({ Search: () => null }))
vi.mock('@/components/theme-switch', () => ({ ThemeSwitch: () => null }))
vi.mock('@/components/config-drawer', () => ({ ConfigDrawer: () => null }))
vi.mock('@/components/profile-dropdown', () => ({ ProfileDropdown: () => null }))

const { useCanMock } = vi.hoisted(() => ({ useCanMock: vi.fn() }))
vi.mock('@/context/permissions-provider', () => ({
  useCan: (...args: unknown[]) => useCanMock(...args),
}))

const HOLIDAYS = {
  data: [
    {
      id: 'h1',
      code: 'NEWYEAR',
      name: "New Year's Day",
      month_day: '01-01',
      type: 'regular',
      region_code: null,
      observe_weekend_as: null,
      multiplier_regular: null,
      multiplier_overtime: null,
      is_recurring: true,
      is_active: true,
      is_deleted: false,
      created_at: null,
      updated_at: null,
    },
  ],
  count: 1,
}

describe('HolidaysPage', () => {
  it('renders the page title and count', async () => {
    useHolidayConfigsMock.mockReturnValue({
      data: HOLIDAYS,
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })
    useCanMock.mockReturnValue(true)

    const { getByText } = await render(<HolidaysPage />)
    await expect.element(getByText('Holiday Configuration')).toBeVisible()
    await expect.element(getByText('1 holiday config')).toBeVisible()
  })

  it('renders holiday config rows', async () => {
    useHolidayConfigsMock.mockReturnValue({
      data: HOLIDAYS,
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })
    useCanMock.mockReturnValue(true)

    const { getByText } = await render(<HolidaysPage />)
    await expect.element(getByText("New Year's Day")).toBeVisible()
    await expect.element(getByText('01-01')).toBeVisible()
  })

  it('shows Add Holiday button when add permission is granted', async () => {
    useHolidayConfigsMock.mockReturnValue({
      data: HOLIDAYS,
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })
    useCanMock.mockReturnValue(true)

    const { container } = await render(<HolidaysPage />)
    const addButtons = container.querySelectorAll('button')
    expect([...addButtons].some(btn => btn.textContent === 'Add Holiday')).toBe(true)
  })

  it('hides Add Holiday button when user lacks add permission', async () => {
    useHolidayConfigsMock.mockReturnValue({
      data: HOLIDAYS,
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })
    useCanMock.mockImplementation((_m: string, action: string) => action === 'view')

    const { container } = await render(<HolidaysPage />)
    const addButtons = container.querySelectorAll('button')
    expect([...addButtons].some(btn => btn.textContent === 'Add Holiday')).toBe(false)
  })

  it('shows empty state when no holiday configs', async () => {
    useHolidayConfigsMock.mockReturnValue({
      data: { data: [], count: 0 },
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })
    useCanMock.mockReturnValue(true)

    const { getByText } = await render(<HolidaysPage />)
    await expect.element(getByText('No holiday configs found.')).toBeVisible()
  })

  it('shows loading state', async () => {
    useHolidayConfigsMock.mockReturnValue({
      data: undefined,
      isPending: true,
      isError: false,
      refetch: vi.fn(),
    })
    useCanMock.mockReturnValue(true)

    const { getByText } = await render(<HolidaysPage />)
    await expect.element(getByText('Loading...')).toBeVisible()
  })

  it('shows retry on error', async () => {
    const refetch = vi.fn()
    useHolidayConfigsMock.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      refetch,
    })
    useCanMock.mockReturnValue(true)

    const { getByText, getByRole } = await render(<HolidaysPage />)
    await expect.element(getByText(/Failed to load holiday configurations/i)).toBeVisible()
    await userEvent.click(getByRole('button', { name: /try again/i }))
    expect(refetch).toHaveBeenCalled()
  })

  it('shows permission denied when not authorized', async () => {
    useCanMock.mockReturnValue(false)

    const { getByText } = await render(<HolidaysPage />)
    await expect
      .element(getByText(/You do not have permission to view holiday configurations/i))
      .toBeVisible()
  })
})
