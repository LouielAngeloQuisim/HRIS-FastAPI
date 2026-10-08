import { renderWithClient } from '@/test-utils/providers'
import { expect, it, vi } from 'vitest'
import { userEvent } from 'vitest/browser'
import SalaryPage from './index'

const mocks = vi.hoisted(() => ({
  canView: vi.fn(),
  employees: vi.fn((_page = 1) => ({
    data: { data: [], count: 0 },
    isPending: false,
  })),
  preflight: vi.fn(
    async (request: { batch_id: string; employee_ids: string[] }) => ({
      batch_id: request.batch_id,
      valid: true,
      requested: request.employee_ids.length,
      replayed: false,
      issues: [],
    })
  ),
  commit: vi.fn(
    async (request: { batch_id: string; employee_ids: string[] }) => ({
      batch_id: request.batch_id,
      replayed: false,
      assignments: request.employee_ids.map((employee_id) => ({
        id: `assignment-${employee_id}`,
        employee_id,
        pay_group_id: 'group-monthly',
        effective_from: '2026-11-01',
        effective_to: null,
      })),
    })
  ),
}))

vi.mock('@/components/layout/header', () => ({ Header: () => <div /> }))
vi.mock('@/context/permissions-provider', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/context/permissions-provider')>()),
  useCan: () => mocks.canView(),
}))
vi.mock('@/lib/api/employees', () => ({
  useEmployees: (page: number) => mocks.employees(page),
}))
vi.mock('@/lib/api/payroll', () => ({
  useCreateSalary: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateSalary: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useDeleteSalary: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useEmployeeSalaries: () => ({
    data: { data: [], count: 0 },
    isPending: false,
    isError: false,
    refetch: vi.fn(),
  }),
  useSalaryRoster: () => ({ data: { data: [], count: 0 } }),
  useBulkSalary: () => ({
    preflight: { mutateAsync: vi.fn(), isPending: false },
    commit: { mutateAsync: vi.fn(), isPending: false },
  }),
  usePayGroupList: () => ({
    data: [
      {
        id: 'group-monthly',
        code: 'MONTHLY',
        name: 'Monthly staff',
        cadence: 'monthly',
        first_period_end_day: null,
        second_period_end_day: null,
        payment_offset_days: 0,
        weekend_rule: 'next_business_day',
        is_active: true,
      },
    ],
    isPending: false,
    isError: false,
  }),
  useBulkPayGroupAssignments: () => ({
    preflight: { mutateAsync: mocks.preflight, isPending: false },
    commit: { mutateAsync: mocks.commit, isPending: false, isError: false },
  }),
}))

it('keeps hook order stable when payroll view permission changes', async () => {
  mocks.canView.mockReturnValue(false)
  const screen = await renderWithClient(<SalaryPage />)
  await expect
    .element(screen.getByText(/do not have permission to view salaries/i))
    .toBeVisible()

  mocks.canView.mockReturnValue(true)
  await screen.rerender(<SalaryPage />)
  await expect
    .element(screen.getByRole('heading', { name: 'Employee Salaries' }))
    .toBeVisible()
})

it('requires explicit employees and successful preflight before bulk pay-group assignment', async () => {
  mocks.canView.mockReturnValue(true)
  mocks.employees.mockReturnValue({
    data: {
      data: [
        {
          id: 'employee-1',
          employee_code: 'E001',
          first_name: 'Jane',
          last_name: 'Doe',
          employee_status: 'Active',
        },
      ],
      count: 1,
    },
    isPending: false,
  })
  const screen = await renderWithClient(<SalaryPage />)

  await userEvent.click(screen.getByTestId('bulk-pay-group-select'))
  await userEvent.click(screen.getByRole('option', { name: /Monthly staff/ }))
  await userEvent.fill(
    screen.getByLabelText('Pay-group effective date'),
    '2026-11-01'
  )
  await userEvent.click(screen.getByLabelText('Assign E001'))
  const commit = screen.getByTestId('pay-group-bulk-commit')
  await expect.element(commit).toBeDisabled()

  await userEvent.click(screen.getByTestId('pay-group-bulk-preflight'))
  await expect.element(commit).not.toBeDisabled()
  await userEvent.click(commit)

  expect(mocks.commit).toHaveBeenCalledWith(
    expect.objectContaining({
      pay_group_id: 'group-monthly',
      effective_from: '2026-11-01',
      employee_ids: ['employee-1'],
    })
  )
})

it('keeps explicit selections while paging through the employee roster', async () => {
  mocks.canView.mockReturnValue(true)
  mocks.employees.mockImplementation((page = 1) => ({
    data: {
      data:
        page === 1
          ? [
              {
                id: 'employee-1',
                employee_code: 'E001',
                first_name: 'Jane',
                last_name: 'Doe',
                employee_status: 'Active',
              },
            ]
          : [
              {
                id: 'employee-2',
                employee_code: 'E002',
                first_name: 'John',
                last_name: 'Doe',
                employee_status: 'Active',
              },
            ],
      count: 501,
    },
    isPending: false,
  }))
  const screen = await renderWithClient(<SalaryPage />)
  await userEvent.click(screen.getByTestId('bulk-pay-group-select'))
  await userEvent.click(screen.getByRole('option', { name: /Monthly staff/ }))
  await userEvent.fill(
    screen.getByLabelText('Pay-group effective date'),
    '2026-11-01'
  )
  await userEvent.click(screen.getByLabelText('Assign E001'))
  await userEvent.click(screen.getByRole('button', { name: 'Next employees' }))
  await expect.element(screen.getByLabelText('Assign E002')).toBeVisible()
  await userEvent.click(screen.getByLabelText('Assign E002'))
  await expect
    .element(screen.getByText('2 employees explicitly selected'))
    .toBeVisible()
  await userEvent.click(screen.getByTestId('pay-group-bulk-preflight'))
  await userEvent.click(screen.getByTestId('pay-group-bulk-commit'))
  expect(mocks.commit).toHaveBeenCalledWith(
    expect.objectContaining({
      employee_ids: ['employee-1', 'employee-2'],
    })
  )
})
