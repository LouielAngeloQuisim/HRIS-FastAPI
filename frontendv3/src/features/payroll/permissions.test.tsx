import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import PayrollPage from './index'

const { useCanMock } = vi.hoisted(() => ({ useCanMock: vi.fn() }))
vi.mock('@/context/permissions-provider', () => ({
  useCan: (...args: unknown[]) => useCanMock(...args),
}))

const { useEmployeesMock, useDepartmentsMock } = vi.hoisted(() => ({
  useEmployeesMock: vi.fn(() => ({
    data: { data: [], count: 0 },
    isPending: false,
    isError: false,
  })),
  useDepartmentsMock: vi.fn(() => ({
    data: { data: [], count: 0 },
    isPending: false,
    isError: false,
  })),
}))
vi.mock('@/lib/api/employees', () => ({
  useEmployees: () => useEmployeesMock(),
}))
vi.mock('@/lib/api/departments', () => ({
  useDepartments: () => useDepartmentsMock(),
}))

vi.mock('@/lib/api/payroll', () => ({
  usePayrollSetup: () => ({
    groups: { data: [], isPending: false, isError: false },
  }),
  usePayrollRunPreflight: () => ({ mutateAsync: vi.fn(), isPending: false }),
  usePayrollAttendanceCalculationPreview: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  usePrepareAttendancePayrollDraft: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  usePreviewPayroll: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useGeneratePayroll: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useApprovePayrollRun: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useVoidPayrollRun: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

describe('PayrollPage permissions', () => {
  it('renders permission denied for view', async () => {
    useCanMock.mockReturnValue(false)

    const screen = await render(<PayrollPage />)
    await expect
      .element(screen.getByText(/You do not have permission to view payroll/i))
      .toBeVisible()
  })
})
