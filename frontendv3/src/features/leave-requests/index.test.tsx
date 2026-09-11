import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import LeaveRequestsPage from './index'

const { refetch } = vi.hoisted(() => ({ refetch: vi.fn() }))

vi.mock('@/context/permissions-provider', () => ({
  useCan: () => true,
}))

vi.mock('@tanstack/react-router', () => ({
  getRouteApi: () => ({ useSearch: () => ({}), useNavigate: () => vi.fn() }),
}))

const { useLeaveRequestsMock, useApproveLeaveRequestMock, useRejectLeaveRequestMock, useSubmitLeaveRequestMock } = vi.hoisted(() => ({
  useLeaveRequestsMock: vi.fn(),
  useApproveLeaveRequestMock: vi.fn(() => ({
    mutateAsync: vi.fn(),
    isPending: false,
  })),
  useRejectLeaveRequestMock: vi.fn(() => ({
    mutateAsync: vi.fn(),
    isPending: false,
  })),
  useSubmitLeaveRequestMock: vi.fn(() => ({
    mutateAsync: vi.fn(),
    isPending: false,
  })),
}))
vi.mock('@/lib/api/leave-requests', () => ({
  useLeaveRequests: (...args: unknown[]) => useLeaveRequestsMock(...args),
  useApproveLeaveRequest: () => useApproveLeaveRequestMock(),
  useRejectLeaveRequest: () => useRejectLeaveRequestMock(),
  useSubmitLeaveRequest: () => useSubmitLeaveRequestMock(),
}))

vi.mock('@/components/layout/header', () => ({
  Header: ({ children }: { children?: React.ReactNode }) => <header>{children}</header>,
}))
vi.mock('@/components/search', () => ({ Search: () => null }))
vi.mock('@/components/theme-switch', () => ({ ThemeSwitch: () => null }))
vi.mock('@/components/config-drawer', () => ({ ConfigDrawer: () => null }))
vi.mock('@/components/profile-dropdown', () => ({ ProfileDropdown: () => null }))

describe('LeaveRequestsPage', () => {
  it('renders the page title', async () => {
    useLeaveRequestsMock.mockReturnValue({
      data: { data: [], count: 0 },
      isPending: false,
      isError: false,
      refetch,
    })

    const screen = await render(<LeaveRequestsPage />)
    await expect.element(screen.getByText('Leave Requests')).toBeVisible()
  })

  it('shows retry button on error', async () => {
    useLeaveRequestsMock.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      refetch,
    })

    const screen = await render(<LeaveRequestsPage />)
    await expect.element(screen.getByText('Failed to load leave requests.')).toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: /try again/i }))
    expect(refetch).toHaveBeenCalled()
  })

  it('shows approve/reject buttons for pending requests', async () => {
    useLeaveRequestsMock.mockReturnValue({
      data: {
        data: [{
          id: 'req-1',
          employee_id: 'emp-1',
          policy_id: 'pol-1',
          enrollment_id: null,
          date_start: '2026-01-01',
          date_end: '2026-01-02',
          total_days_requested: 2,
          requested_hours: null,
          status: 'pending',
          reason: 'Vacation',
          document_ref: null,
          decision_note: null,
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

    const screen = await render(<LeaveRequestsPage />)
    await expect.element(screen.getByRole('button', { name: 'Approve' })).toBeVisible()
    await expect.element(screen.getByRole('button', { name: 'Reject' })).toBeVisible()
  })

  it('does not show approve/reject for approved requests', async () => {
    useLeaveRequestsMock.mockReturnValue({
      data: {
        data: [{
          id: 'req-1',
          employee_id: 'emp-1',
          policy_id: 'pol-1',
          enrollment_id: null,
          date_start: '2026-01-01',
          date_end: '2026-01-02',
          total_days_requested: 2,
          requested_hours: null,
          status: 'approved',
          reason: 'Vacation',
          document_ref: null,
          decision_note: null,
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

    const screen = await render(<LeaveRequestsPage />)
    await expect.element(screen.getByText('approved', { exact: true })).toBeVisible()
  })

  it('approve button is disabled when mutation is pending', async () => {
    useApproveLeaveRequestMock.mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: true,
    })
    useRejectLeaveRequestMock.mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    })
    useLeaveRequestsMock.mockReturnValue({
      data: {
        data: [{
          id: 'req-1',
          employee_id: 'emp-1',
          policy_id: 'pol-1',
          enrollment_id: null,
          date_start: '2026-01-01',
          date_end: '2026-01-02',
          total_days_requested: 2,
          requested_hours: null,
          status: 'pending',
          reason: 'Vacation',
          document_ref: null,
          decision_note: null,
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

    const screen = await render(<LeaveRequestsPage />)
    const approveBtn = screen.getByRole('button', { name: 'Approve' })
    await expect.element(approveBtn).toBeDisabled()
  })
})
