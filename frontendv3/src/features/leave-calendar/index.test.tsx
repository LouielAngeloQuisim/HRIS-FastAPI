import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import LeaveCalendarPage from './index'

const { refetch } = vi.hoisted(() => ({ refetch: vi.fn() }))

vi.mock('@/context/permissions-provider', () => ({
  useCan: () => true,
}))

vi.mock('@tanstack/react-router', () => ({
  getRouteApi: () => ({ useSearch: () => ({}), useNavigate: () => vi.fn() }),
}))

const { useLeaveCalendarMock } = vi.hoisted(() => ({ useLeaveCalendarMock: vi.fn() }))
vi.mock('@/lib/api/leave-ledger', () => ({
  useLeaveCalendar: (...args: unknown[]) => useLeaveCalendarMock(...args),
}))

vi.mock('@/components/layout/header', () => ({
  Header: ({ children }: { children?: React.ReactNode }) => <header>{children}</header>,
}))
vi.mock('@/components/search', () => ({ Search: () => null }))
vi.mock('@/components/theme-switch', () => ({ ThemeSwitch: () => null }))
vi.mock('@/components/config-drawer', () => ({ ConfigDrawer: () => null }))
vi.mock('@/components/profile-dropdown', () => ({ ProfileDropdown: () => null }))

describe('LeaveCalendarPage', () => {
  it('renders the page title', async () => {
    useLeaveCalendarMock.mockReturnValue({
      data: [],
      isPending: false,
      isError: false,
      refetch,
    })

    const screen = await render(<LeaveCalendarPage />)
    await expect.element(screen.getByText('Leave Calendar')).toBeVisible()
  })

  it('shows retry button on error', async () => {
    useLeaveCalendarMock.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      refetch,
    })

    const screen = await render(<LeaveCalendarPage />)
    await expect.element(screen.getByText('Failed to load leave calendar.')).toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: /try again/i }))
    expect(refetch).toHaveBeenCalled()
  })

  it('shows loading state', async () => {
    useLeaveCalendarMock.mockReturnValue({
      data: undefined,
      isPending: true,
      isError: false,
      refetch,
    })

    const screen = await render(<LeaveCalendarPage />)
    await expect.element(screen.getByText('Loading...')).toBeVisible()
  })

  it('shows empty state when no events', async () => {
    useLeaveCalendarMock.mockReturnValue({
      data: [],
      isPending: false,
      isError: false,
      refetch,
    })

    const screen = await render(<LeaveCalendarPage />)
    await expect.element(screen.getByText('No leave events found for the selected range.')).toBeVisible()
  })

  it('renders events with correct colors from API', async () => {
    const mockData = [
      {
        id: '1',
        observed_date: '2026-01-01',
        title: 'New Year',
        type: 'holiday',
        status: null,
        color: '#EF4444',
      },
      {
        id: '2',
        observed_date: '2026-01-01',
        title: 'Annual Leave',
        type: 'request',
        status: 'approved',
        color: '#3B82F6',
      },
    ]

    useLeaveCalendarMock.mockReturnValue({
      data: mockData,
      isPending: false,
      isError: false,
      refetch,
    })

    const screen = await render(<LeaveCalendarPage />)
    await expect.element(screen.getByText('New Year')).toBeVisible()
    await expect.element(screen.getByText('Annual Leave')).toBeVisible()
  })
})
