import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import PayrollPage from './index'

const { useCanMock } = vi.hoisted(() => ({ useCanMock: vi.fn() }))
vi.mock('@/context/permissions-provider', () => ({
  useCan: (...args: unknown[]) => useCanMock(...args),
}))

const { usePreviewPayrollMock } = vi.hoisted(() => ({ usePreviewPayrollMock: vi.fn() }))
vi.mock('@/lib/api/payroll', () => ({
  usePreviewPayroll: () => usePreviewPayrollMock(),
  useGeneratePayroll: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useApprovePayrollRun: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useVoidPayrollRun: () => ({ mutateAsync: vi.fn(), isPending: false }),
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

vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => vi.fn(),
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

describe('PayrollPage data fidelity', () => {
  it('renders backend preview values without client-side recomputation', async () => {
    useCanMock.mockReturnValue(true)
    usePreviewPayrollMock.mockReturnValue({ mutateAsync: vi.fn().mockResolvedValue(PREVIEW_ENTRIES), isPending: false })

    const screen = await render(<PayrollPage />)
    const dateFromInput = screen.getByTestId('date-from-input')
    const dateToInput = screen.getByTestId('date-to-input')
    await dateFromInput.fill('2026-09-01')
    await dateToInput.fill('2026-09-30')
    await screen.getByTestId('preview-payroll-button').click()

    await vi.waitFor(() => {
      expect(screen.getByText('Review Payroll Entries')).toBeVisible()
    })

    await expect.element(screen.getByText('emp-1')).toBeVisible()
    await expect.element(screen.getByText(/25,000/)).toBeVisible()
    await expect.element(screen.getByText(/23,000/)).toBeVisible()
  })
})
