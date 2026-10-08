import { renderWithClient } from '@/test-utils/providers'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { userEvent } from 'vitest/browser'
import PayrollPage from './index'

const { canView, setup, preflight, calculation, prepare, ledger } = vi.hoisted(
  () => ({
    canView: vi.fn((..._args: unknown[]) => true),
    setup: vi.fn(),
    preflight: vi.fn(),
    calculation: vi.fn(),
    prepare: vi.fn(),
    ledger: vi.fn(),
  })
)

vi.mock('@/context/permissions-provider', () => ({
  useCan: (...args: unknown[]) => canView(...args),
}))
vi.mock('@/lib/api/payroll', () => ({
  usePayrollSetup: () => setup(),
  usePayrollContributionLedger: (...args: unknown[]) => ledger(...args),
  usePayrollRunPreflight: () => ({
    mutateAsync: (...args: unknown[]) => preflight(...args),
    isPending: false,
  }),
  usePayrollAttendanceCalculationPreview: () => ({
    mutateAsync: (...args: unknown[]) => calculation(...args),
    isPending: false,
  }),
  usePrepareAttendancePayrollDraft: () => ({
    mutateAsync: (...args: unknown[]) => prepare(...args),
    isPending: false,
  }),
}))

const baseSetup = () => ({
  groups: {
    data: [
      {
        id: 'group-1',
        code: 'SM',
        name: 'Twice monthly',
        cadence: 'semi_monthly',
      },
    ],
    isPending: false,
    isError: false,
  },
})

describe('Payroll readiness page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    canView.mockReturnValue(true)
    setup.mockReturnValue(baseSetup())
    ledger.mockReturnValue({ data: null, isPending: false, isError: false })
  })

  it('shows the expected roster readiness page and keeps payroll execution paused', async () => {
    const screen = await renderWithClient(<PayrollPage />)
    await expect
      .element(screen.getByRole('heading', { name: 'Payroll readiness' }))
      .toBeVisible()
    await expect
      .element(screen.getByRole('status'))
      .toHaveTextContent(/final approval also requires.*system approval gate/i)
    await expect
      .element(screen.getByTestId('payroll-preflight-button'))
      .toBeDisabled()
  })

  it('denies the page when payroll view permission is absent', async () => {
    canView.mockReturnValue(false)
    const screen = await renderWithClient(<PayrollPage />)
    await expect
      .element(screen.getByText(/do not have permission to view payroll/i))
      .toBeVisible()
  })

  it('shows finalized statutory collections and reasoned correction links', async () => {
    ledger.mockReturnValue({
      data: {
        count: 2,
        data: [
          {
            id: 'ledger-1',
            employee_id: 'employee-1',
            employee_code: 'QA001',
            employee_name: 'QA Employee',
            payroll_entry_id: 'entry-1',
            scheme: 'pagibig',
            contribution_month: '2026-10-01',
            sequence: 1,
            monthly_basis: '26000.00',
            employee_amount: '-10.00',
            employer_amount: '0.00',
            source_references: ['https://www.pagibigfund.gov.ph/'],
            adjustment_reason: 'Correct an over-collection',
            reverses_id: 'ledger-base',
            created_at: '2026-10-31T00:00:00Z',
          },
        ],
      },
      isPending: false,
      isError: false,
      isFetching: false,
    })
    const screen = await renderWithClient(<PayrollPage />)
    await userEvent.fill(screen.getByTestId('payroll-ledger-month'), '2026-10')
    await userEvent.fill(
      screen.getByTestId('payroll-ledger-employee-code'),
      'QA001'
    )
    await expect
      .element(
        screen.getByRole('heading', { name: 'Contribution reconciliation' })
      )
      .toBeVisible()
    await expect.element(screen.getByText(/QA001 · QA Employee/)).toBeVisible()
    await expect
      .element(screen.getByText('Correction', { exact: true }))
      .toBeVisible()
    await expect
      .element(screen.getByText('Correct an over-collection'))
      .toBeVisible()
    await expect.element(screen.getByText(/Reverses ledger-base/)).toBeVisible()
    expect(ledger).toHaveBeenCalledWith(
      expect.objectContaining({
        month: '2026-10',
        scheme: '',
        employeeCode: 'QA001',
        skip: 0,
      })
    )
  })

  it('submits a selected configured period and displays named blockers', async () => {
    preflight.mockResolvedValue({
      pay_group_id: 'group-1',
      date_from: '2026-09-01',
      date_to: '2026-09-15',
      policy_versions: [],
      count: 2,
      blocked_count: 1,
      ready_count: 1,
      has_more: false,
      entries: [
        {
          employee_id: 'employee-1',
          employee_code: 'QA001',
          employee_name: 'QA Employee',
          email: null,
          blockers: [
            {
              code: 'missing_salary',
              message: 'No effective salary.',
              work_date: '2026-09-01',
            },
          ],
          warnings: [],
          attendance_records: 0,
          eligible_overtime_minutes: 0,
          approved_overtime_minutes: 0,
        },
        {
          employee_id: 'employee-2',
          employee_code: 'QA002',
          employee_name: 'QA Employee With Email Warning',
          email: null,
          blockers: [],
          warnings: [
            'No employee email is on file; payslip delivery will need an authorized address correction.',
          ],
          attendance_records: 2,
          eligible_overtime_minutes: 0,
          approved_overtime_minutes: 0,
        },
      ],
    })
    const screen = await renderWithClient(<PayrollPage />)
    await userEvent.click(screen.getByTestId('payroll-pay-group-select'))
    await userEvent.click(
      screen.getByRole('option', { name: /Twice monthly/i })
    )
    await userEvent.fill(
      screen.getByTestId('payroll-period-from'),
      '2026-09-01'
    )
    await userEvent.fill(screen.getByTestId('payroll-period-to'), '2026-09-15')
    await userEvent.click(screen.getByTestId('payroll-preflight-button'))
    await expect.element(screen.getByText(/QA001 · QA Employee/)).toBeVisible()
    await expect.element(screen.getByText(/No effective salary/i)).toBeVisible()
    await expect
      .element(screen.getByText(/No employee email is on file/))
      .toBeVisible()
    await expect
      .element(screen.getByText('Ready for calculation review'))
      .toBeVisible()
    expect(preflight).toHaveBeenCalledWith(
      expect.objectContaining({
        pay_group_id: 'group-1',
        date_from: '2026-09-01',
        date_to: '2026-09-15',
      })
    )
  })

  it('shows a provisional earnings preview and clearly excludes statutory deductions', async () => {
    calculation.mockResolvedValue({
      pay_group_id: 'group-1',
      date_from: '2026-09-01',
      date_to: '2026-09-15',
      calculation_status: 'provisional_earnings_only',
      count: 1,
      has_more: false,
      entries: [
        {
          employee_id: 'employee-1',
          employee_code: 'QA001',
          employee_name: 'QA Employee',
          regular_earnings: '12000.00',
          approved_overtime: '450.00',
          holiday_premium: '130.00',
          attendance_deduction: '0.00',
          gross_before_statutory: '12580.00',
          blockers: [],
          formula: ['2026-09-01: hourly basis'],
          source_references: ['attendance:example:revision:1'],
        },
      ],
    })
    const screen = await renderWithClient(<PayrollPage />)
    await userEvent.click(screen.getByTestId('payroll-pay-group-select'))
    await userEvent.click(
      screen.getByRole('option', { name: /Twice monthly/i })
    )
    await userEvent.fill(
      screen.getByTestId('payroll-period-from'),
      '2026-09-01'
    )
    await userEvent.fill(screen.getByTestId('payroll-period-to'), '2026-09-15')
    await userEvent.click(
      screen.getByTestId('payroll-attendance-preview-button')
    )
    await expect
      .element(screen.getByText(/provisional earnings only/i))
      .toBeVisible()
    await expect.element(screen.getByText(/QA001 · QA Employee/)).toBeVisible()
    await expect.element(screen.getByText('Holiday premium')).toBeVisible()
    await expect.element(screen.getByText('130.00')).toBeVisible()
    await expect.element(screen.getByText('12580.00')).toBeVisible()
    expect(calculation).toHaveBeenCalledWith(
      expect.objectContaining({
        pay_group_id: 'group-1',
        date_from: '2026-09-01',
        date_to: '2026-09-15',
      })
    )
  })

  it('creates a blocked draft and explains it cannot be finalized', async () => {
    prepare.mockResolvedValue({ id: 'run-12345678', workflow_status: 'draft' })
    const screen = await renderWithClient(<PayrollPage />)
    await userEvent.click(screen.getByTestId('payroll-pay-group-select'))
    await userEvent.click(
      screen.getByRole('option', { name: /Twice monthly/i })
    )
    await userEvent.fill(
      screen.getByTestId('payroll-period-from'),
      '2026-09-01'
    )
    await userEvent.fill(screen.getByTestId('payroll-period-to'), '2026-09-15')
    await userEvent.click(screen.getByTestId('payroll-prepare-draft-button'))
    await expect
      .element(screen.getByText(/Draft saved: run-12345678/))
      .toBeVisible()
    expect(prepare).toHaveBeenCalledWith({
      pay_group_id: 'group-1',
      date_from: '2026-09-01',
      date_to: '2026-09-15',
    })
  })
})
