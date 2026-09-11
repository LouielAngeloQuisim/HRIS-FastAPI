import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import LeaveCalendarPage from './index'

const { refetch } = vi.hoisted(() => ({ refetch: vi.fn() }))

vi.mock('@/context/permissions-provider', () => ({
  useCan: () => true,
}))

vi.mock('@/tanstack/react-router', () => ({
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

describe('LeaveCalendarPage (data fidelity)', () => {
  it('renders events grouped by date with colors from API', async () => {
    useLeaveCalendarMock.mockReturnValue({
      data: [
        { id: '1', observed_date: '2026-01-01', title: 'New Year', type: 'holiday', status: null, color: '#EF4444' },
        { id: '2', observed_date: '2026-01-01', title: 'Leave', type: 'request', status: 'approved', color: '#3B82F6' },
        { id: '3', observed_date: '2026-01-02', title: 'Leave 2', type: 'request', status: 'pending', color: '#10B981' },
      ],
      isPending: false,
      isError: false,
      refetch,
    })

    const screen = await render(<LeaveCalendarPage />)
    await expect.element(screen.getByText('New Year')).toBeVisible()
    await expect.element(screen.getByText('Leave', { exact: true })).toBeVisible()
    await expect.element(screen.getByText('Leave 2')).toBeVisible()
  })
})
