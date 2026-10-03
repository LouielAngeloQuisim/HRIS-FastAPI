import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import PayrollRunsPage from './index'

const { usePayrollRunsMock } = vi.hoisted(() => ({ usePayrollRunsMock: vi.fn() }))
vi.mock('@/lib/api/payroll', () => ({
  usePayrollRuns: (...args: unknown[]) => usePayrollRunsMock(...args),
}))

const { useCanMock } = vi.hoisted(() => ({ useCanMock: vi.fn() }))
vi.mock('@/context/permissions-provider', () => ({
  useCan: (...args: unknown[]) => useCanMock(...args),
}))

vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => vi.fn(),
}))

const RUNS = {
  data: [
    {
      id: 'run-1',
      cutoff_type: 'monthly',
      date_from: '2026-09-01',
      date_to: '2026-09-30',
      status: 'draft',
      adjustment_type: 'regular',
      created_by: null,
      is_deleted: false,
      created_at: null,
      updated_at: null,
    },
  ],
  count: 1,
}

describe('PayrollRunsPage', () => {
  it('renders the payroll runs title', async () => {
    usePayrollRunsMock.mockReturnValue({ data: RUNS, isPending: false, isError: false, refetch: vi.fn() })
    useCanMock.mockReturnValue(true)

    const screen = await render(<PayrollRunsPage />)
    await expect.element(screen.getByText('Payroll Runs')).toBeVisible()
  })

  it('shows permission denied when not authorized', async () => {
    useCanMock.mockReturnValue(false)

    const screen = await render(<PayrollRunsPage />)
    await expect.element(screen.getByText(/You do not have permission to view payroll runs/i)).toBeVisible()
  })

  it('renders run rows from mocked API', async () => {
    usePayrollRunsMock.mockReturnValue({ data: RUNS, isPending: false, isError: false, refetch: vi.fn() })
    useCanMock.mockReturnValue(true)

    const screen = await render(<PayrollRunsPage />)
    await expect.element(screen.getByText('run-1')).toBeVisible()
    await expect.element(screen.getByText('draft')).toBeVisible()
  })

  it('shows empty state when no runs', async () => {
    usePayrollRunsMock.mockReturnValue({ data: { data: [], count: 0 }, isPending: false, isError: false, refetch: vi.fn() })
    useCanMock.mockReturnValue(true)

    const screen = await render(<PayrollRunsPage />)
    await expect.element(screen.getByText('0 runs')).toBeVisible()
  })
})
