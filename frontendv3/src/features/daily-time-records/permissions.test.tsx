import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { type useDailyTimeRecords } from '@/lib/api/daily-time-records'
import DailyTimeRecordsPage from './index'

const { useApproveOvertimeMock, useRejectOvertimeMock } = vi.hoisted(() => ({
  useApproveOvertimeMock: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
  useRejectOvertimeMock: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
}))

describe('DailyTimeRecordsPage (permissions)', () => {
  it('denies access when user lacks view permission', async () => {
    vi.mock('@/context/permissions-provider', () => ({
      useCan: () => false,
    }))

    const { useDailyTimeRecordsMock } = vi.hoisted(() => ({ useDailyTimeRecordsMock: vi.fn((..._args: Parameters<typeof useDailyTimeRecords>) => ({ data: undefined, isPending: false, isError: false, refetch: vi.fn() })) }))
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
    await expect.element(screen.getByText('You do not have permission to view daily time records.')).toBeVisible()
  })
})
