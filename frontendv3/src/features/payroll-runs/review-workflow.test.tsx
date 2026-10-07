import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import { PayrollRunDetail } from './detail'

const {
  usePayrollRunMock,
  startReviewMock,
  reviewEntryMock,
  finalizeMock,
  rebuildDraftMock,
  deliveryStatusMock,
  correctAddressMock,
  resendDeliveryMock,
  downloadPayslipMock,
  useCanMock,
  navigateMock,
} = vi.hoisted(() => ({
  usePayrollRunMock: vi.fn(),
  startReviewMock: vi.fn(),
  reviewEntryMock: vi.fn(),
  finalizeMock: vi.fn(),
  rebuildDraftMock: vi.fn(),
  deliveryStatusMock: vi.fn(),
  correctAddressMock: vi.fn(),
  resendDeliveryMock: vi.fn(),
  downloadPayslipMock: vi.fn(),
  useCanMock: vi.fn(),
  navigateMock: vi.fn(),
}))

vi.mock('@/lib/api/payroll', () => ({
  usePayrollRun: (...args: unknown[]) => usePayrollRunMock(...args),
  useApprovePayrollRun: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useVoidPayrollRun: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useStartPayrollReview: () => ({
    mutateAsync: startReviewMock,
    isPending: false,
  }),
  useRebuildAttendancePayrollDraft: () => ({
    mutateAsync: rebuildDraftMock,
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
  usePayrollDeliveryStatus: (...args: unknown[]) => deliveryStatusMock(...args),
  downloadPayrollPayslip: (...args: unknown[]) => downloadPayslipMock(...args),
  useCorrectPayrollDeliveryAddress: () => ({
    mutateAsync: correctAddressMock,
    isPending: false,
  }),
  useResendPayrollDelivery: () => ({
    mutateAsync: resendDeliveryMock,
    isPending: false,
  }),
}))

vi.mock('@/context/permissions-provider', () => ({
  useCan: (...args: unknown[]) => useCanMock(...args),
}))

vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => navigateMock,
  useParams: () => ({ runId: 'run-1' }),
}))

const entry = {
  id: 'entry-1',
  payroll_run_id: 'run-1',
  employee_id: 'employee-1',
  employee_name: null as string | null,
  employee_code: null as string | null,
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
  input_fingerprint: 'f'.repeat(64),
  payroll_finalization_enabled: true,
  payslip_delivery_enabled: false,
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
    rebuildDraftMock.mockResolvedValue({ id: 'replacement-run' })
    deliveryStatusMock.mockReturnValue({
      data: [],
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })
    correctAddressMock.mockResolvedValue({})
    resendDeliveryMock.mockResolvedValue({})
    downloadPayslipMock.mockResolvedValue(undefined)
    vi.spyOn(window, 'confirm').mockReturnValue(true)
  })

  it('shows draft blockers and directs HR to resolve or explicitly exclude them', async () => {
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

  it('lets HR explicitly exclude a blocked entry with a reason', async () => {
    usePayrollRunMock.mockReturnValue({
      data: run('in_review'),
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })

    const screen = await render(<PayrollRunDetail />)
    const reason = screen.getByRole('textbox', { name: 'Exclusion reason' })
    await userEvent.fill(reason, 'Employee setup is incomplete for this period')
    await userEvent.click(
      screen.getByRole('button', { name: 'Exclude with reason' })
    )

    await expect
      .poll(() => reviewEntryMock)
      .toHaveBeenCalledWith({
        entryId: 'entry-1',
        action: 'excluded',
        expected_input_fingerprint: 'a'.repeat(64),
        reason: 'Employee setup is incomplete for this period',
      })
  })

  it('shows calculation lines and named source-revision counts', async () => {
    usePayrollRunMock.mockReturnValue({
      data: run('in_review', { ...entry, review_state: 'ready', blockers: [] }),
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })

    const screen = await render(<PayrollRunDetail />)
    await userEvent.click(
      screen.getByText('Calculation breakdown and source history')
    )

    await expect
      .element(screen.getByText(/Formula: gross earnings/))
      .toBeVisible()
    await expect.element(screen.getByText('regular')).toBeVisible()
    await expect.element(screen.getByText('Source revisions')).toBeVisible()
    await expect
      .element(screen.getByText('Attendance', { exact: true }))
      .toBeVisible()
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

  it('rebuilds a blocked draft from current inputs with an audit reason', async () => {
    usePayrollRunMock.mockReturnValue({
      data: run('draft'),
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })
    vi.spyOn(window, 'prompt').mockReturnValue('Updated attendance and salary')

    const screen = await render(<PayrollRunDetail />)
    await userEvent.click(
      screen.getByRole('button', { name: 'Rebuild blocked draft' })
    )

    await expect
      .poll(() => rebuildDraftMock)
      .toHaveBeenCalledWith({
        expected_run_fingerprint: 'f'.repeat(64),
        reason: 'Updated attendance and salary',
      })
    await expect
      .poll(() => navigateMock)
      .toHaveBeenCalledWith({
        to: '/payroll-runs/$runId',
        params: { runId: 'replacement-run' },
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

  it('shows employee identity and lets payroll editors retry a failed payslip with a reason', async () => {
    usePayrollRunMock.mockReturnValue({
      data: run('finalized', {
        ...entry,
        employee_name: 'Ava Worker',
        employee_code: 'EMP-104',
        review_state: 'reviewed',
        blockers: [],
      }),
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })
    deliveryStatusMock.mockReturnValue({
      data: [
        {
          id: 'delivery-1',
          payroll_entry_id: 'entry-1',
          document_version: 1,
          recipient_snapshot: 'ava@example.test',
          status: 'failed',
          attempts: 2,
          next_attempt_at: null,
          sent_at: null,
          last_error_code: 'smtp_rejected',
          last_action_reason: null,
        },
      ],
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })

    const screen = await render(<PayrollRunDetail />)
    await expect
      .element(screen.getByText('Ava Worker (EMP-104)', { exact: true }))
      .toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: 'Download PDF' }))
    await expect
      .poll(() => downloadPayslipMock)
      .toHaveBeenCalledWith('run-1', 'entry-1')
    await userEvent.type(
      screen.getByLabelText('Action reason'),
      'HR verified address'
    )
    await userEvent.click(
      screen.getByRole('button', { name: 'Retry delivery' })
    )
    await expect
      .poll(() => resendDeliveryMock)
      .toHaveBeenCalledWith({
        jobId: 'delivery-1',
        payload: {
          reason: 'HR verified address',
          confirm_duplicate_risk: false,
        },
      })
  })
})
