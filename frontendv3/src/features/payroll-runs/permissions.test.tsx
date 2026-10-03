import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import PayrollRunsPage from './index'

const { useCanMock } = vi.hoisted(() => ({ useCanMock: vi.fn() }))
vi.mock('@/context/permissions-provider', () => ({
  useCan: (...args: unknown[]) => useCanMock(...args),
}))

vi.mock('@/lib/api/payroll', () => ({
  usePayrollRuns: () => ({ data: { data: [], count: 0 }, isPending: false, isError: false, refetch: vi.fn() }),
}))

describe('PayrollRunsPage permissions', () => {
  it('renders permission denied for view', async () => {
    useCanMock.mockReturnValue(false)

    const screen = await render(<PayrollRunsPage />)
    await expect.element(screen.getByText(/You do not have permission to view payroll runs/i)).toBeVisible()
  })
})
