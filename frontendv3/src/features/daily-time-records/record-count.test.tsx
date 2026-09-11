import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import DailyTimeRecordsPage from './index'

const { refetch } = vi.hoisted(() => ({ refetch: vi.fn() }))

vi.mock('@/context/permissions-provider', () => ({
  useCan: () => true,
}))

vi.mock('@/tanstack/react-router', () => ({
  getRouteApi: () => ({ useSearch: () => ({}), useNavigate: () => vi.fn() }),
}))

const { useDailyTimeRecordsMock, useApproveOvertimeMock, useRejectOvertimeMock } = vi.hoisted(() => ({
  useDailyTimeRecordsMock: vi.fn(),
  useApproveOvertimeMock: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
  useRejectOvertimeMock: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
}))
vi.mock('@/lib/api/daily-time-records', () => ({
  useDailyTimeRecords: (...args: unknown[]) => useDailyTimeRecordsMock(...args),
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

describe('DailyTimeRecordsPage (record count)', () => {
  it('displays the count from the API response', async () => {
    useDailyTimeRecordsMock.mockReturnValue({
      data: { data: [], count: 42 },
      isPending: false,
      isError: false,
      refetch,
    })

    const screen = await render(<DailyTimeRecordsPage />)
    await expect.element(screen.getByText('42 records')).toBeVisible()
  })
})
