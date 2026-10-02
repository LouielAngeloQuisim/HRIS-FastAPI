vi.mock('@/lib/api/employees', () => ({ useEmployees: () => ({ data: { data: [{ id: 'emp-1', employee_code: 'EMP1', first_name: 'Test', last_name: 'Employee' }] }, isPending: false }) }))
import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
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

describe('LeaveCalendarPage (retry)', () => {
  it('calls refetch when retry is clicked', async () => {
    refetch.mockClear()
    useLeaveCalendarMock.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      refetch,
    })

    const screen = await render(<LeaveCalendarPage />)
    if (document.querySelector('#leave-calendar-employee')) {
      await userEvent.selectOptions(document.querySelector('#leave-calendar-employee')!, 'emp-1')
    }
    await userEvent.click(screen.getByRole('button', { name: /try again/i }))
    expect(refetch).toHaveBeenCalled()
  })
})
