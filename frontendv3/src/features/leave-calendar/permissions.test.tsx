import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import LeaveCalendarPage from './index'

describe('LeaveCalendarPage (permissions)', () => {
  it('denies access when user lacks view permission', async () => {
    vi.mock('@/context/permissions-provider', () => ({
      useCan: () => false,
    }))

    const { useLeaveCalendarMock } = vi.hoisted(() => ({ useLeaveCalendarMock: vi.fn(() => ({ data: [], isPending: false, isError: false, refetch: vi.fn() })) }))
    vi.mock('@/lib/api/leave-ledger', () => ({
      useLeaveCalendar: (...args: any[]) => (useLeaveCalendarMock as any)(...args),
    }))

    vi.mock('@/components/layout/header', () => ({
      Header: ({ children }: { children?: React.ReactNode }) => <header>{children}</header>,
    }))
    vi.mock('@/components/search', () => ({ Search: () => null }))
    vi.mock('@/components/theme-switch', () => ({ ThemeSwitch: () => null }))
    vi.mock('@/components/config-drawer', () => ({ ConfigDrawer: () => null }))
    vi.mock('@/components/profile-dropdown', () => ({ ProfileDropdown: () => null }))

    const screen = await render(<LeaveCalendarPage />)
    await expect.element(screen.getByText('You do not have permission to view leave calendar.')).toBeVisible()
  })
})
