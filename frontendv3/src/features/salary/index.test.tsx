import { renderWithClient } from '@/test-utils/providers'
import { expect, it, vi } from 'vitest'
import SalaryPage from './index'

const { canView } = vi.hoisted(() => ({ canView: vi.fn() }))

vi.mock('@/components/layout/header', () => ({ Header: () => <div /> }))
vi.mock('@/context/permissions-provider', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/context/permissions-provider')>()),
  useCan: () => canView(),
}))
vi.mock('@/lib/api/employees', () => ({
  useEmployees: () => ({ data: { data: [], count: 0 }, isPending: false }),
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
}))

it('keeps hook order stable when payroll view permission changes', async () => {
  canView.mockReturnValue(false)
  const screen = await renderWithClient(<SalaryPage />)
  await expect
    .element(screen.getByText(/do not have permission to view salaries/i))
    .toBeVisible()

  canView.mockReturnValue(true)
  await screen.rerender(<SalaryPage />)
  await expect
    .element(screen.getByRole('heading', { name: 'Employee Salaries' }))
    .toBeVisible()
})
