import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import { PayrollRunDetail } from './detail'

const {
  usePayrollRunMock,
  startReviewMock,
  reviewEntryMock,
  finalizeMock,
  useCanMock,
} = vi.hoisted(() => ({
  usePayrollRunMock: vi.fn(),
  startReviewMock: vi.fn(),
  reviewEntryMock: vi.fn(),
  finalizeMock: vi.fn(),
  useCanMock: vi.fn(),
}))

vi.mock('@/lib/api/payroll', () => ({
  usePayrollRun: (...args: unknown[]) => usePayrollRunMock(...args),
  useApprovePayrollRun: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useVoidPayrollRun: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useStartPayrollReview: () => ({
    mutateAsync: startReviewMock,
    isPending: false,
  }),
  useReviewPayrollEntry: () => ({
    mutateAsync: reviewEntryMock,
    isPending: false,
  }),
  useFinalizePayrollRun: () => ({
    mutateAsync: finalizeMock,
    isPending: false,
  }),
}))

vi.mock('@/context/permissions-provider', () => ({
  useCan: (...args: unknown[]) => useCanMock(...args),
}))

vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => vi.fn(),
  useParams: () => ({ runId: 'run-1' }),
}))

const entry = {
  id: 'entry-1',
  payroll_run_id: 'run-1',
  employee_id: 'employee-1',
  basic_rate: '26000.00',
  rate_date_from: '2026-10-01',
  rate_date_to: '2026-10-31',
  earnings: { regular: '26000.00' },
  deductions: {},
  gross_pay: '26000.00',
  total_deductions: '0.00',
  net_pay: '26000.00',
  overtime_pay: '0.00',
  thirteenth_month: '0.00',
  non_taxable_income: '0.00',
  taxable_income: '26000.00',
  review_state: 'blocked' as 'blocked' | 'ready' | 'reviewed' | 'excluded',
  reviewed_by: null,
  reviewed_at: null,
  calculation_version: 'attendance-v1-provisional',
  input_fingerprint: 'a'.repeat(64),
  input_snapshot: {},
  blockers: [
    {
      code: 'statutory_calculation_unavailable',
      message: 'Statutory tables are unverified.',
    },
  ],
  created_at: null,
}

const run = (workflow_status: string, reviewEntry = entry) => ({
  id: 'run-1',
  cutoff_type: 'monthly' as const,
  date_from: '2026-10-01',
  date_to: '2026-10-31',
  status: 'draft' as const,
  adjustment_type: 'regular' as const,
  workflow_status,
  pay_group_id: 'group-1',
  policy_version_id: 'policy-1',
  created_by: 'preparer-1',
  is_deleted: false,
  created_at: null,
  updated_at: null,
  total_gross_pay: '26000.00',
  total_deductions: '0.00',
  total_net_pay: '26000.00',
  entries: [reviewEntry],
})

describe('PayrollRunDetail review workflow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useCanMock.mockReturnValue(true)
    startReviewMock.mockResolvedValue({})
    reviewEntryMock.mockResolvedValue({})
    finalizeMock.mockResolvedValue({})
    vi.spyOn(window, 'confirm').mockReturnValue(true)
  })

  it('shows draft blockers and keeps blocked entries out of employee review', async () => {
    usePayrollRunMock.mockReturnValue({
      data: run('draft'),
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })

    const screen = await render(<PayrollRunDetail />)

    await expect
      .element(screen.getByText('Statutory tables are unverified.'))
      .toBeVisible()
    await expect
      .element(screen.getByRole('button', { name: 'Start employee review' }))
      .toBeVisible()
    await expect
      .element(screen.getByRole('button', { name: 'Mark reviewed' }))
      .not.toBeInTheDocument()
  })

  it('sends the entry fingerprint and requires a reason for exclusion', async () => {
    usePayrollRunMock.mockReturnValue({
      data: run('in_review', { ...entry, review_state: 'ready', blockers: [] }),
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })

    const screen = await render(<PayrollRunDetail />)
    await expect
      .element(screen.getByRole('button', { name: 'Mark reviewed' }))
      .toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: 'Mark reviewed' }))
    await expect
      .poll(() => reviewEntryMock)
      .toHaveBeenCalledWith({
        entryId: 'entry-1',
        action: 'reviewed',
        expected_input_fingerprint: 'a'.repeat(64),
        reason: undefined,
      })
  })

  it('offers separate final approval and warns that this schedules payslips only', async () => {
    useCanMock.mockImplementation(
      (_module: string, action: string) =>
        action === 'view' || action === 'approve'
    )
    usePayrollRunMock.mockReturnValue({
      data: run('ready_for_finalization', {
        ...entry,
        review_state: 'reviewed',
        blockers: [],
      }),
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })

    const screen = await render(<PayrollRunDetail />)
    await expect
      .element(screen.getByText(/does not confirm a bank payout/i))
      .toBeVisible()
    await userEvent.click(
      screen.getByRole('button', { name: 'Finalize and schedule payslips' })
    )
    await expect.poll(() => finalizeMock).toHaveBeenCalledWith(undefined)
  })
})
