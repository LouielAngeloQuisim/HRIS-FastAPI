import { type Mock, describe, expect, it, vi } from 'vitest'
import { renderWithClient as render } from '@/test-utils/providers'
import { type useDailyTimeRecords } from '@/lib/api/daily-time-records'
import DailyTimeRecordsPage from './index'

vi.mock('@/context/permissions-provider', () => ({
  useCan: () => true,
}))

vi.mock('@/tanstack/react-router', () => ({
  getRouteApi: () => ({ useSearch: () => ({}), useNavigate: () => vi.fn() }),
}))

const { useDailyTimeRecordsMock, useApproveOvertimeMock, useRejectOvertimeMock } = vi.hoisted(() => ({
  useDailyTimeRecordsMock: vi.fn() as Mock<(...args: Parameters<typeof useDailyTimeRecords>) => unknown>,
  useApproveOvertimeMock: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
  useRejectOvertimeMock: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
}))
vi.mock('@/lib/api/daily-time-records', () => ({
  useDeleteDailyTimeRecord: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateDailyTimeRecord: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useDailyTimeRecords: (...args: Parameters<typeof useDailyTimeRecords>) => useDailyTimeRecordsMock(...args),
  useApproveOvertime: () => useApproveOvertimeMock(),
  useRejectOvertime: () => useRejectOvertimeMock(),
  useDtrIntervals: () => ({ data: [], isPending: false, isError: false }),
  useReplaceDtrIntervals: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock('@/components/layout/header', () => ({
  Header: ({ children }: { children?: React.ReactNode }) => <header>{children}</header>,
}))
vi.mock('@/components/search', () => ({ Search: () => null }))
vi.mock('@/components/theme-switch', () => ({ ThemeSwitch: () => null }))
vi.mock('@/components/config-drawer', () => ({ ConfigDrawer: () => null }))
vi.mock('@/components/profile-dropdown', () => ({ ProfileDropdown: () => null }))

describe('DailyTimeRecordsPage (header)', () => {
  it('renders the page heading', async () => {
    useDailyTimeRecordsMock.mockReturnValue({
      data: { data: [], count: 0 },
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })

    const screen = await render(<DailyTimeRecordsPage />)
    await expect.element(screen.getByRole('heading', { name: 'Daily Time Records' })).toBeVisible()
  })
})

vi.mock('@/lib/api/relationship-labels', async () => ({ ...await import('@/lib/api/relationship-label-text'), useRelationshipLabels: () => ({ data: {} }) }))
