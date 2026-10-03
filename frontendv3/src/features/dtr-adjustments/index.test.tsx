import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import DtrAdjustmentsPage from './index'

const { refetch } = vi.hoisted(() => ({ refetch: vi.fn() }))

const { useDtrAdjustmentsMock, useApproveDtrAdjustmentMock, useRejectDtrAdjustmentMock, useCreateDtrAdjustmentMock } = vi.hoisted(() => ({
  useDtrAdjustmentsMock: vi.fn(),
  useApproveDtrAdjustmentMock: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
  useRejectDtrAdjustmentMock: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
  useCreateDtrAdjustmentMock: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
}))

vi.mock('@/context/permissions-provider', () => ({
  useCan: () => true,
}))

vi.mock('@/tanstack/react-router', () => ({
  getRouteApi: () => ({ useSearch: () => ({}), useNavigate: () => vi.fn() }),
}))

vi.mock('@/lib/api/dtr-adjustments', () => ({
  useDtrAdjustments: (...args: unknown[]) => useDtrAdjustmentsMock(...args),
  useApproveDtrAdjustment: () => useApproveDtrAdjustmentMock(),
  useRejectDtrAdjustment: () => useRejectDtrAdjustmentMock(),
  useCreateDtrAdjustment: () => useCreateDtrAdjustmentMock(),
}))

vi.mock('@/components/layout/header', () => ({
  Header: ({ children }: { children?: React.ReactNode }) => <header>{children}</header>,
}))
vi.mock('@/components/search', () => ({ Search: () => null }))
vi.mock('@/components/theme-switch', () => ({ ThemeSwitch: () => null }))
vi.mock('@/components/config-drawer', () => ({ ConfigDrawer: () => null }))
vi.mock('@/components/profile-dropdown', () => ({ ProfileDropdown: () => null }))

describe('DtrAdjustmentsPage', () => {
  it('renders the page title', async () => {
    useDtrAdjustmentsMock.mockReturnValue({
      data: { data: [], count: 0 },
      isPending: false,
      isError: false,
      refetch,
    })

    const screen = await render(<DtrAdjustmentsPage />)
    await expect.element(screen.getByText('DTR Adjustments')).toBeVisible()
  })

  it('shows retry button on error', async () => {
    useDtrAdjustmentsMock.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      refetch,
    })

    const screen = await render(<DtrAdjustmentsPage />)
    await expect.element(screen.getByText('Failed to load DTR adjustments.')).toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: /try again/i }))
    expect(refetch).toHaveBeenCalled()
  })

  it('shows approve/reject buttons for PENDING adjustments (QA-03: API sends UPPERCASE)', async () => {
    useDtrAdjustmentsMock.mockReturnValue({
      data: {
        data: [{
          id: 'adj-1',
          daily_time_record_id: 'dtr-1',
          employee_id: 'emp-1',
          original_login_date: '2026-01-01T08:00:00',
          original_logout_date: '2026-01-01T17:00:00',
          adjusted_login_date: '2026-01-01T08:30:00',
          adjusted_logout_date: '2026-01-01T17:30:00',
          reason: 'Clock in late',
          status: 'PENDING',
          adjusted_date: null,
          created_by: 'user-1',
          approved_by: null,
          is_deleted: false,
          created_at: null,
          updated_at: null,
        }],
        count: 1,
      },
      isPending: false,
      isError: false,
      refetch,
    })

    const screen = await render(<DtrAdjustmentsPage />)
    await expect.element(screen.getByRole('button', { name: 'Approve' })).toBeVisible()
    await expect.element(screen.getByRole('button', { name: 'Reject' })).toBeVisible()
  })

  it('hides approve/reject for APPROVED and REJECTED rows and colors statuses (QA-03)', async () => {
    const row = (id: string, status: string) => ({
      id,
      daily_time_record_id: 'dtr-' + id,
      employee_id: 'emp-1',
      original_login_date: '2026-01-01T08:00:00',
      original_logout_date: '2026-01-01T17:00:00',
      adjusted_login_date: '2026-01-01T08:30:00',
      adjusted_logout_date: '2026-01-01T17:30:00',
      reason: 'r',
      status,
      adjusted_date: null,
      created_by: 'user-1',
      approved_by: 'user-2',
      is_deleted: false,
      created_at: null,
      updated_at: null,
    })
    useDtrAdjustmentsMock.mockReturnValue({
      data: {
        data: [row('adj-ok', 'APPROVED'), row('adj-no', 'REJECTED')],
        count: 2,
      },
      isPending: false,
      isError: false,
      refetch,
    })

    const screen = await render(<DtrAdjustmentsPage />)
    await expect.element(screen.getByRole('button', { name: 'Approve' })).not.toBeInTheDocument()
    await expect.element(screen.getByRole('button', { name: 'Reject' })).not.toBeInTheDocument()
    const approved = await screen.getByText('APPROVED').element()
    expect(approved.className).toContain('bg-green-100')
    const rejected = await screen.getByText('REJECTED').element()
    expect(rejected.className).toContain('bg-red-100')
  })
})
