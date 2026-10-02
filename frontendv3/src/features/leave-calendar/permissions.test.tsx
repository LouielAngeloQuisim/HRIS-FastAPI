import { userEvent } from 'vitest/browser'
vi.mock('@/lib/api/employees', () => ({ useEmployees: () => ({ data: { data: [{ id: 'emp-1', employee_code: 'EMP1', first_name: 'Test', last_name: 'Employee' }] }, isPending: false }) }))
import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { type useLeaveCalendar } from '@/lib/api/leave-ledger'
import LeaveCalendarPage from './index'

describe('LeaveCalendarPage (permissions)', () => {
  it('denies access when user lacks view permission', async () => {
    vi.mock('@/context/permissions-provider', () => ({
      useCan: () => false,
    }))

    const { useLeaveCalendarMock } = vi.hoisted(() => ({ useLeaveCalendarMock: vi.fn((..._args: Parameters<typeof useLeaveCalendar>) => ({ data: [], isPending: false, isError: false, refetch: vi.fn() })) }))
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

    const screen = await render(<LeaveCalendarPage />)
    if (document.querySelector('#leave-calendar-employee')) {
      await userEvent.selectOptions(document.querySelector('#leave-calendar-employee')!, 'emp-1')
    }
    await expect.element(screen.getByText('You do not have permission to view leave calendar.')).toBeVisible()
  })
})
