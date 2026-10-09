import { describe, expect, it, vi } from 'vitest'
import { renderWithClient as render } from '@/test-utils/providers'
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
  useDeleteDailyTimeRecord: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateDailyTimeRecord: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useDailyTimeRecords: (...args: unknown[]) => useDailyTimeRecordsMock(...args),
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

  it('sends employee and Manila date filters to the query hook', async () => {
    useDailyTimeRecordsMock.mockReturnValue({
      data: { data: [], count: 0 },
      isPending: false,
      isError: false,
      refetch,
    })

    const screen = await render(<DailyTimeRecordsPage />)
    await userEvent.fill(screen.getByRole('textbox', { name: 'Filter by employee code' }), 'EMP-204')
    await userEvent.fill(screen.getByLabelText('Filter from date'), '2026-08-01')
    await userEvent.fill(screen.getByLabelText('Filter to date'), '2026-08-15')

    await expect.poll(() => useDailyTimeRecordsMock.mock.calls.slice(-1)[0]).toEqual([
      1,
      500,
      undefined,
      '2026-08-01',
      '2026-08-15',
      'EMP-204',
    ])
    await expect.element(screen.getByRole('button', { name: 'Clear filters' })).toBeVisible()
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

vi.mock('@/lib/api/relationship-labels', async () => ({ ...await import('@/lib/api/relationship-label-text'), useRelationshipLabels: () => ({ data: {} }) }))
