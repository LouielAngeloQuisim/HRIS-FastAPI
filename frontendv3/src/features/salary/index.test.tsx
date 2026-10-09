import { renderWithClient } from '@/test-utils/providers'
import { expect, it, vi } from 'vitest'
import { userEvent } from 'vitest/browser'
import SalaryPage from './index'

type SalaryPageEmployee = {
  id: string
  employee_code: string
  first_name: string
  last_name: string
  employee_status: string
}

const mocks = vi.hoisted(() => ({
  canView: vi.fn(),
  employees: vi.fn((_page: number) => ({
    data: { data: [] as SalaryPageEmployee[], count: 0 },
    isPending: false,
  })),
  salaryRoster: vi.fn((_missing: boolean, _skip: number, _limit: number, _search: string) => ({
    data: { data: [] as Array<{ employee_id: string; employee_code: string; first_name: string; last_name: string; employee_status: string; has_effective_salary: boolean }>, count: 0 },
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
  incrementPreview: vi.fn(async (request: { batch_id: string; employee_ids: string[] }) => ({
    batch_id: request.batch_id,
    valid: true,
    replayed: false,
    issues: [],
    changes: request.employee_ids.map(employee_id => ({
      employee_id,
      employee_code: 'E001',
      employee_name: 'Jane Doe',
      current_salary_id: `salary-${employee_id}`,
      current_rate: '15000.00',
      proposed_rate: '15050.00',
      pay_type: 'monthly' as const,
    })),
    salaries: [],
  })),
  incrementCommit: vi.fn(async (request: { batch_id: string }) => ({
    batch_id: request.batch_id,
    valid: true,
    replayed: false,
    issues: [],
    changes: [],
    salaries: [{ id: 'salary-new', employee_id: 'employee-1', basic_rate: '15050.00' }],
  })),
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
  useSalaryRoster: (missing: boolean, skip = 0, limit = 500, search = '') =>
    mocks.salaryRoster(missing, skip, limit, search),
  useBulkSalary: () => ({
    preflight: { mutateAsync: vi.fn(), isPending: false },
    commit: { mutateAsync: vi.fn(), isPending: false },
  }),
  useBulkSalaryIncrement: () => ({
    preview: { mutateAsync: mocks.incrementPreview, isPending: false },
    commit: { mutateAsync: mocks.incrementCommit, isPending: false, isError: false },
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

it('previews and applies a shared increase only to explicitly selected employees', async () => {
  mocks.canView.mockReturnValue(true)
  mocks.employees.mockReturnValue({
    data: {
      data: [{ id: 'employee-1', employee_code: 'E001', first_name: 'Jane', last_name: 'Doe', employee_status: 'Active' }],
      count: 1,
    },
    isPending: false,
  })
  mocks.salaryRoster.mockReturnValue({
    data: { data: [{ employee_id: 'employee-1', employee_code: 'E001', first_name: 'Jane', last_name: 'Doe', employee_status: 'Active', has_effective_salary: true }], count: 1 },
  })
  const screen = await renderWithClient(<SalaryPage />)
  await userEvent.fill(screen.getByLabelText('Salary increment employee search'), 'E001')
  await userEvent.click(screen.getByTestId('salary-increment-search'))
  expect(mocks.salaryRoster).toHaveBeenLastCalledWith(false, 0, 500, 'E001')
  await userEvent.click(screen.getByLabelText('Select E001 for increase'))
  await userEvent.fill(screen.getByLabelText('Salary increase effective date'), '2026-11-01')
  await userEvent.fill(screen.getByLabelText('Salary increase amount'), '50.00')

  const commit = screen.getByTestId('salary-increment-commit')
  await expect.element(commit).toBeDisabled()
  await userEvent.click(screen.getByTestId('salary-increment-preview'))
  await expect.element(screen.getByText(/₱15000.00 → ₱15050.00/)).toBeVisible()
  await expect.element(commit).not.toBeDisabled()
  await userEvent.click(commit)
  expect(mocks.incrementCommit).toHaveBeenCalledWith(expect.objectContaining({
    effective_date: '2026-11-01',
    increment: '50.00',
    employee_ids: ['employee-1'],
  }))
})

it('retains salary-increment selections across employee pages', async () => {
  mocks.canView.mockReturnValue(true)
  mocks.employees.mockImplementation((page = 1) => ({
    data: {
      data: page === 1
        ? [{ id: 'employee-1', employee_code: 'E001', first_name: 'Jane', last_name: 'Doe', employee_status: 'Active' }]
        : [{ id: 'employee-2', employee_code: 'E002', first_name: 'John', last_name: 'Doe', employee_status: 'Active' }],
      count: 501,
    },
    isPending: false,
  }))
  mocks.salaryRoster.mockImplementation((_missing, skip) => ({
    data: {
      data: skip === 0
        ? [{ employee_id: 'employee-1', employee_code: 'E001', first_name: 'Jane', last_name: 'Doe', employee_status: 'Active', has_effective_salary: true }]
        : [{ employee_id: 'employee-2', employee_code: 'E002', first_name: 'John', last_name: 'Doe', employee_status: 'Active', has_effective_salary: true }],
      count: 501,
    },
  }))
  const screen = await renderWithClient(<SalaryPage />)
  await userEvent.click(screen.getByLabelText('Select E001 for increase'))
  await userEvent.click(screen.getByTestId('salary-increment-next-page'))
  await userEvent.click(screen.getByLabelText('Select E002 for increase'))
  await userEvent.fill(screen.getByLabelText('Salary increase effective date'), '2026-11-01')
  await userEvent.click(screen.getByTestId('salary-increment-preview'))
  expect(mocks.incrementPreview).toHaveBeenLastCalledWith(expect.objectContaining({
    employee_ids: ['employee-1', 'employee-2'],
  }))
})

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
  await userEvent.click(screen.getByTestId('pay-group-next-page'))
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
