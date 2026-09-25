import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { type useDailyTimeRecords } from '@/lib/api/daily-time-records'
import DailyTimeRecordsPage from './index'

const { useApproveOvertimeMock, useRejectOvertimeMock } = vi.hoisted(() => ({
  useApproveOvertimeMock: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
  useRejectOvertimeMock: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
}))

describe('DailyTimeRecordsPage (row actions)', () => {
  it('hides Edit button when user lacks edit permission', async () => {
    vi.mock('@/context/permissions-provider', () => ({
      useCan: (_module: string, action: string) => action === 'view',
    }))

    const { useDailyTimeRecordsMock } = vi.hoisted(() => ({ useDailyTimeRecordsMock: vi.fn((..._args: Parameters<typeof useDailyTimeRecords>) => ({ data: { data: [{ id: '1', employee_id: 'emp-1', login_date: null, logout_date: null, rendered_minutes: 480, late_minutes: 0, undertime_minutes: 0, overtime_minutes: 0, overtime_approved: null, is_absent: false, source: 'test' }], count: 1 }, isPending: false, isError: false, refetch: vi.fn() })) }))
    vi.mock('@/lib/api/daily-time-records', () => ({
      useDailyTimeRecords: (...args: Parameters<typeof useDailyTimeRecords>) => useDailyTimeRecordsMock(...args),
      useApproveOvertime: () => useApproveOvertimeMock(),
      useRejectOvertime: () => useRejectOvertimeMock(),
    }))

    vi.mock('@/components/layout/header', () => ({
      Header: ({ children }: { children?: React.ReactNode }) => <header>{children}</header>,
    }))
    vi.mock('@/components/search', () => ({ Search: () => null }))
    vi.mock('@/components/theme-switch', () => ({ ThemeSwitch: () => null }))
    vi.mock('@/components/config-drawer', () => ({ ConfigDrawer: () => null }))
    vi.mock('@/components/profile-dropdown', () => ({ ProfileDropdown: () => null }))

    const screen = await render(<DailyTimeRecordsPage />)
    const editButtons = screen.container.querySelectorAll('button')
    expect([...editButtons].some(btn => btn.textContent === 'Edit')).toBe(false)
  })
})
