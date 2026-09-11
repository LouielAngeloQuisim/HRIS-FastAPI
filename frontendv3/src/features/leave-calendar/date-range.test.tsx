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

describe('LeaveCalendarPage (date range)', () => {
  it('has date inputs for filtering', async () => {
    useLeaveCalendarMock.mockReturnValue({
      data: [],
      isPending: false,
      isError: false,
      refetch,
    })

    const screen = await render(<LeaveCalendarPage />)
    const dateInputs = screen.container.querySelectorAll('input[type="date"]')
    expect(dateInputs.length).toBe(2)
  })

  it('calls refetch when Apply button is clicked', async () => {
    refetch.mockClear()
    useLeaveCalendarMock.mockReturnValue({
      data: [],
      isPending: false,
      isError: false,
      refetch,
    })

    const screen = await render(<LeaveCalendarPage />)
    const applyButton = screen.getByRole('button', { name: /apply/i })
    await userEvent.click(applyButton)
    expect(refetch).toHaveBeenCalled()
  })
})
