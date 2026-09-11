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

describe('DailyTimeRecordsPage (data fidelity)', () => {
  it('renders backend numbers byte-for-byte without recomputation', async () => {
    const apiResponse = {
      data: {
        data: [
          {
            id: '1',
            employee_id: 'emp-1',
            login_date: '2026-01-01T08:00:00',
            logout_date: '2026-01-01T17:00:00',
            rendered_minutes: 480,
            late_minutes: 15,
            undertime_minutes: 0,
            overtime_minutes: 30,
            is_absent: false,
            source: 'biometric',
          },
        ],
        count: 1,
      },
      isPending: false,
      isError: false,
      refetch,
    }

    useDailyTimeRecordsMock.mockReturnValue(apiResponse)

    const screen = await render(<DailyTimeRecordsPage />)
    await expect.element(screen.getByText('480')).toBeVisible()
    await expect.element(screen.getByText('15')).toBeVisible()
    await expect.element(screen.getByText('30')).toBeVisible()
  })
})
