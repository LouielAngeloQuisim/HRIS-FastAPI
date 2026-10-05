import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import PayrollPage from './index'

const { usePreviewPayrollMock, useGeneratePayrollMock, useApprovePayrollRunMock, useVoidPayrollRunMock } = vi.hoisted(() => ({
  usePreviewPayrollMock: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
  useGeneratePayrollMock: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
  useApprovePayrollRunMock: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
  useVoidPayrollRunMock: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
}))
vi.mock('@/lib/api/payroll', () => ({
  usePreviewPayroll: () => usePreviewPayrollMock(),
  useGeneratePayroll: () => useGeneratePayrollMock(),
  useApprovePayrollRun: () => useApprovePayrollRunMock(),
  useVoidPayrollRun: () => useVoidPayrollRunMock(),
}))

const { useEmployeesMock, useDepartmentsMock } = vi.hoisted(() => ({
  useEmployeesMock: vi.fn(() => ({ data: { data: [], count: 0 }, isPending: false, isError: false })),
  useDepartmentsMock: vi.fn(() => ({ data: { data: [], count: 0 }, isPending: false, isError: false })),
}))
vi.mock('@/lib/api/employees', () => ({
  useEmployees: () => useEmployeesMock(),
}))
vi.mock('@/lib/api/departments', () => ({
  useDepartments: () => useDepartmentsMock(),
}))

const { useCanMock } = vi.hoisted(() => ({ useCanMock: vi.fn() }))
vi.mock('@/context/permissions-provider', () => ({
  useCan: (...args: unknown[]) => useCanMock(...args),
}))

const { navigateMock } = vi.hoisted(() => ({ navigateMock: vi.fn() }))
vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => navigateMock,
}))

const PREVIEW_ENTRIES = [
  {
    employee_id: 'emp-1',
    basic_rate: '25000',
    rate_date_from: '2026-09-01',
    rate_date_to: '2026-09-30',
    earnings: {},
    deductions: {},
    gross_pay: '28000',
    total_deductions: '5000',
    net_pay: '23000',
    overtime_pay: '3000',
    thirteenth_month: '0',
    non_taxable_income: '0',
    taxable_income: '23000',
  },
]

const PREVIEW_ENTRIES_WITH_WARNINGS = [
  {
    ...PREVIEW_ENTRIES[0],
    warnings: [
      { code: 'pending_leave', message: 'Pending leave request(s) covering this period: 2026-09-10 to 2026-09-15' },
      { code: 'missing_dtr', message: '5 scheduled workday(s) with no DTR record; treated as unexcused absence' },
    ],
  },
]

describe('PayrollPage', () => {
  it('renders the payroll execution title', async () => {
    useCanMock.mockReturnValue(true)
    usePreviewPayrollMock.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })

    const screen = await render(<PayrollPage />)
    await expect.element(screen.getByText('Payroll Execution')).toBeVisible()
  })

  it('shows permission denied when not authorized', async () => {
    useCanMock.mockReturnValue(false)

    const screen = await render(<PayrollPage />)
    await expect.element(screen.getByText(/You do not have permission to view payroll/i)).toBeVisible()
  })

  it('calls preview mutation with cutoff type and dates', async () => {
    useCanMock.mockReturnValue(true)
    usePreviewPayrollMock.mockReturnValue({ mutateAsync: vi.fn().mockResolvedValue(PREVIEW_ENTRIES), isPending: false })

    const screen = await render(<PayrollPage />)
    const dateFromInput = screen.getByTestId('date-from-input')
    const dateToInput = screen.getByTestId('date-to-input')
    await dateFromInput.fill('2026-09-01')
    await dateToInput.fill('2026-09-30')
    await userEvent.click(screen.getByTestId('cutoff-type-select'))
    await userEvent.click(screen.getByRole('option', { name: 'Monthly', exact: true }))
    await userEvent.click(screen.getByTestId('preview-payroll-button'))

    await vi.waitFor(() => {
      expect(usePreviewPayrollMock().mutateAsync).toHaveBeenCalledTimes(1)
    })
  })

  it('shows review step after preview', async () => {
    useCanMock.mockReturnValue(true)
    usePreviewPayrollMock.mockReturnValue({ mutateAsync: vi.fn().mockResolvedValue(PREVIEW_ENTRIES), isPending: false })

    const screen = await render(<PayrollPage />)
    const dateFromInput = screen.getByTestId('date-from-input')
    const dateToInput = screen.getByTestId('date-to-input')
    await dateFromInput.fill('2026-09-01')
    await dateToInput.fill('2026-09-30')
    await userEvent.click(screen.getByTestId('cutoff-type-select'))
    await userEvent.click(screen.getByRole('option', { name: 'Monthly', exact: true }))
    await userEvent.click(screen.getByTestId('preview-payroll-button'))

    await vi.waitFor(() => {
      expect(screen.getByText('Review Payroll Entries')).toBeVisible()
    })
  })

  it('displays compliance warnings in review step when present', async () => {
    useCanMock.mockReturnValue(true)
    usePreviewPayrollMock.mockReturnValue({ mutateAsync: vi.fn().mockResolvedValue(PREVIEW_ENTRIES_WITH_WARNINGS), isPending: false })

    const screen = await render(<PayrollPage />)
    const dateFromInput = screen.getByTestId('date-from-input')
    const dateToInput = screen.getByTestId('date-to-input')
    await dateFromInput.fill('2026-09-01')
    await dateToInput.fill('2026-09-30')
    await userEvent.click(screen.getByTestId('cutoff-type-select'))
    await userEvent.click(screen.getByRole('option', { name: 'Monthly', exact: true }))
    await userEvent.click(screen.getByTestId('preview-payroll-button'))

    await vi.waitFor(() => {
      expect(screen.getByTestId('compliance-warnings')).toBeVisible()
    })
    await expect.element(screen.getByText(/Pending leave request/i)).toBeVisible()
    await expect.element(screen.getByText(/missing_dtr/i)).toBeVisible()
  })
  it('requires server recalculation after edits and carries the reviewed overtime into generation', async () => {
    useCanMock.mockReturnValue(true)
    const preview = vi.fn().mockResolvedValueOnce(PREVIEW_ENTRIES).mockResolvedValueOnce([{ ...PREVIEW_ENTRIES[0], overtime_pay: '500.25' }])
    const generate = vi.fn().mockResolvedValue({ id: 'run-1', status: 'draft' })
    usePreviewPayrollMock.mockReturnValue({ mutateAsync: preview, isPending: false })
    useGeneratePayrollMock.mockReturnValue({ mutateAsync: generate, isPending: false })
    const screen = await render(<PayrollPage />)
    await screen.getByTestId('date-from-input').fill('2026-10-01')
    await screen.getByTestId('date-to-input').fill('2026-10-31')
    await userEvent.click(screen.getByTestId('preview-payroll-button'))
    await expect.element(screen.getByTestId('edit-overtime-emp-1')).toBeVisible()
    await screen.getByTestId('edit-overtime-emp-1').fill('500.25')
    await expect.element(screen.getByTestId('proceed-to-review-button')).toBeDisabled()
    await userEvent.click(screen.getByTestId('recalculate-payroll-button'))
    await expect.element(screen.getByTestId('proceed-to-review-button')).toBeEnabled()
    expect(preview.mock.calls[1][0].entries).toEqual([{ employee_id: 'emp-1', overtime_pay: '500.25' }])
    await userEvent.click(screen.getByTestId('proceed-to-review-button'))
    await vi.waitFor(() => expect(generate).toHaveBeenCalledOnce())
    expect(generate.mock.calls[0][0].entries).toEqual([{ employee_id: 'emp-1', overtime_pay: '500.25' }])
  })

  it('offers salary setup recovery when preview reports a missing salary', async () => {
    useCanMock.mockReturnValue(true)
    navigateMock.mockClear()
    usePreviewPayrollMock.mockReturnValue({ mutateAsync: vi.fn().mockRejectedValue({ response: { data: { detail: 'Employee emp-1 has no active salary record' } } }), isPending: false })
    const screen = await render(<PayrollPage />)
    await screen.getByTestId('date-from-input').fill('2026-10-01')
    await screen.getByTestId('date-to-input').fill('2026-10-31')
    await userEvent.click(screen.getByTestId('preview-payroll-button'))
    await expect.element(screen.getByTestId('missing-salary-recovery')).toBeVisible()
    await userEvent.click(screen.getByTestId('open-salary-setup-button'))
    expect(navigateMock).toHaveBeenCalledWith({ to: '/payroll/salary' })
  })

  it('locks uncertain generation edits and retries with the same identity and payload', async () => {
    useCanMock.mockReturnValue(true)
    usePreviewPayrollMock.mockReturnValue({ mutateAsync: vi.fn().mockResolvedValue(PREVIEW_ENTRIES), isPending: false })
    const generate = vi.fn().mockRejectedValueOnce(new Error('Lost response')).mockResolvedValueOnce({ id: 'run-1', status: 'draft' })
    useGeneratePayrollMock.mockReturnValue({ mutateAsync: generate, isPending: false })
    const screen = await render(<PayrollPage />)
    await screen.getByTestId('date-from-input').fill('2026-10-01')
    await screen.getByTestId('date-to-input').fill('2026-10-31')
    await userEvent.click(screen.getByTestId('preview-payroll-button'))
    await expect.element(screen.getByTestId('proceed-to-review-button')).toBeVisible()
    await userEvent.click(screen.getByTestId('proceed-to-review-button'))
    await expect.element(screen.getByTestId('generation-outcome-unknown')).toBeVisible()
    await expect.element(screen.getByTestId('recalculate-payroll-button')).toBeDisabled()
    await expect.element(screen.getByTestId('edit-overtime-emp-1')).toBeDisabled()
    await userEvent.click(screen.getByTestId('proceed-to-review-button'))
    await vi.waitFor(() => expect(generate).toHaveBeenCalledTimes(2))
    expect(generate.mock.calls[0][0]).toEqual(generate.mock.calls[1][0])
    expect(generate.mock.calls[0][0].request_id).toMatch(/^[0-9a-f-]{36}$/)
    await expect.element(screen.getByRole('heading', { name: 'Payroll Run Generated' })).toBeVisible()
  })

})
