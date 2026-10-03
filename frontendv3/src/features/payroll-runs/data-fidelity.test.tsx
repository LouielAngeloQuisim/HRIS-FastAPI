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

describe('PayrollRunsPage data fidelity', () => {
  it('renders backend run values without client-side recomputation', async () => {
    usePayrollRunsMock.mockReturnValue({ data: RUNS, isPending: false, isError: false, refetch: vi.fn() })
    useCanMock.mockReturnValue(true)

    const screen = await render(<PayrollRunsPage />)
    await expect.element(screen.getByText('run-1')).toBeVisible()
    await expect.element(screen.getByText('draft')).toBeVisible()
    await expect.element(screen.getByText('2026-09-01 → 2026-09-30')).toBeVisible()
  })
})
