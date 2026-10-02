import { userEvent } from 'vitest/browser'
vi.mock('@/lib/api/employees', () => ({ useEmployees: () => ({ data: { data: [{ id: 'emp-1', employee_code: 'EMP1', first_name: 'Test', last_name: 'Employee' }] }, isPending: false }) }))
import { type Mock, describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { type useLeaveCalendar } from '@/lib/api/leave-ledger'
import LeaveCalendarPage from './index'

const { refetch } = vi.hoisted(() => ({ refetch: vi.fn() }))

vi.mock('@/context/permissions-provider', () => ({
  useCan: () => true,
}))

vi.mock('@/tanstack/react-router', () => ({
  getRouteApi: () => ({ useSearch: () => ({}), useNavigate: () => vi.fn() }),
}))

const { useLeaveCalendarMock } = vi.hoisted(() => ({ useLeaveCalendarMock: vi.fn() as Mock<(...args: Parameters<typeof useLeaveCalendar>) => unknown> }))
vi.mock('@/lib/api/leave-ledger', () => ({
  useLeaveCalendar: (...args: Parameters<typeof useLeaveCalendar>) => useLeaveCalendarMock(...args),
}))

vi.mock('@/components/layout/header', () => ({
  Header: ({ children }: { children?: React.ReactNode }) => <header>{children}</header>,
}))
vi.mock('@/components/search', () => ({ Search: () => null }))
vi.mock('@/components/theme-switch', () => ({ ThemeSwitch: () => null }))
vi.mock('@/components/config-drawer', () => ({ ConfigDrawer: () => null }))
vi.mock('@/components/profile-dropdown', () => ({ ProfileDropdown: () => null }))

describe('LeaveCalendarPage (header)', () => {
  it('renders the page heading', async () => {
    useLeaveCalendarMock.mockReturnValue({
      data: [],
      isPending: false,
      isError: false,
      refetch,
    })

    const screen = await render(<LeaveCalendarPage />)
    if (document.querySelector('#leave-calendar-employee')) {
      await userEvent.selectOptions(document.querySelector('#leave-calendar-employee')!, 'emp-1')
    }
    await expect.element(screen.getByRole('heading', { name: 'Leave Calendar' })).toBeVisible()
  })
})
