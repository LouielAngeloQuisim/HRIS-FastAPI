import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import DailyTimeRecordsPage from './index'

const { refetch } = vi.hoisted(() => ({ refetch: vi.fn() }))

vi.mock('@/context/permissions-provider', () => ({
  useCan: () => true,
}))

vi.mock('@tanstack/react-router', () => ({
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

describe('DailyTimeRecordsPage', () => {
  it('renders the page title', async () => {
    useDailyTimeRecordsMock.mockReturnValue({
      data: { data: [], count: 0 },
      isPending: false,
      isError: false,
      refetch,
    })

    const screen = await render(<DailyTimeRecordsPage />)
    await expect.element(screen.getByText('Daily Time Records')).toBeVisible()
  })

  it('shows retry button on error', async () => {
    useDailyTimeRecordsMock.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      refetch,
    })

    const screen = await render(<DailyTimeRecordsPage />)
    await expect.element(screen.getByText('Failed to load daily time records.')).toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: /try again/i }))
    expect(refetch).toHaveBeenCalled()
  })

  it('shows loading state', async () => {
    useDailyTimeRecordsMock.mockReturnValue({
      data: undefined,
      isPending: true,
      isError: false,
      refetch,
    })

    const screen = await render(<DailyTimeRecordsPage />)
    await expect.element(screen.getByText('Loading...')).toBeVisible()
  })

  it('shows empty state when no records', async () => {
    useDailyTimeRecordsMock.mockReturnValue({
      data: { data: [], count: 0 },
      isPending: false,
      isError: false,
      refetch,
    })

    const screen = await render(<DailyTimeRecordsPage />)
    await expect.element(screen.getByText('No records found.')).toBeVisible()
  })

  it('renders rows from mocked API without client-side recomputation', async () => {
    const mockData = {
      data: [
        {
          id: '1',
          employee_id: 'emp-1',
          login_date: '2026-01-01T08:00:00',
          logout_date: '2026-01-01T17:00:00',
          rendered_minutes: 480,
          late_minutes: 0,
          undertime_minutes: 0,
          overtime_minutes: 30,
          is_absent: false,
          source: 'biometric',
        },
      ],
      count: 1,
    }

    useDailyTimeRecordsMock.mockReturnValue({
      data: mockData,
      isPending: false,
      isError: false,
      refetch,
    })

    const screen = await render(<DailyTimeRecordsPage />)
    await expect.element(screen.getByText('480')).toBeVisible()
    await expect.element(screen.getByText('30')).toBeVisible()
  })
})
