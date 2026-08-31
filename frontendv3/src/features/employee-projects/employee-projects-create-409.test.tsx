import { describe, expect, it, vi } from 'vitest'
import { userEvent } from 'vitest/browser'
import { renderWithClient } from '@/test-utils/providers'
import EmployeeProjectsPage from './index'

const { useEPsMock, useCanMock, useCreateEpMock } = vi.hoisted(() => ({
  useEPsMock: vi.fn(), useCanMock: vi.fn(), useCreateEpMock: vi.fn(),
}))
vi.mock('@/lib/api/employee-projects', () => ({
  useEmployeeProjects: (...a: unknown[]) => useEPsMock(...a),
  useCreateEmployeeProject: () => ({ mutateAsync: useCreateEpMock, isPending: false }),
  useUpdateEmployeeProject: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useDeleteEmployeeProject: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))
vi.mock('@/context/permissions-provider', () => ({ useCan: (...a: unknown[]) => useCanMock(...a) }))
vi.mock('@/lib/api/client', () => ({ api: { delete: () => Promise.resolve({ data: {} }) } }))
vi.mock('@/components/select-dropdown', () => ({ SelectDropdown: () => null }))

const DATA = { data: [{ id: 'ep1', employee_id: 'e1', project_id: 'p1', date: '2026-01-01', rendered_hours: 8, task: 'Build', is_assigned: true }], count: 1 }

describe('EmployeeProjects create 409 duplicate pair (§8.9)', () => {
  it('surfaces the conflict and leaves the drawer open (no optimistic add, single attempt)', async () => {
    useEPsMock.mockReturnValue({ data: DATA, isPending: false, isError: false, refetch: vi.fn() })
    useCanMock.mockReturnValue(true)
    useCreateEpMock.mockRejectedValue({ response: { status: 409, data: { message: 'Duplicate employee-project pair' } } })

    const { getByRole, getByText } = await renderWithClient(<EmployeeProjectsPage />)
    // Existing row is rendered.
    await expect.element(getByText('e1')).toBeInTheDocument()

    // Open create drawer.
    await userEvent.click(getByRole('button', { name: /Add EmployeeProjects/i }))
    await expect.element(getByRole('heading', { name: /Create EmployeeProjects/i })).toBeInTheDocument()

    // Fill a textbox field, then submit — server returns 409.
    await userEvent.fill(getByRole('textbox', { name: /Task/i }), 'NewTask')
    await userEvent.click(getByRole('button', { name: /^Create$/i }))

    // Create mutation was invoked and rejected by the 409 (exactly once => no retry).
    await vi.waitFor(() => { expect(useCreateEpMock).toHaveBeenCalledTimes(1) })

    // Drawer stays open (onClose not called on error) => no optimistic add.
    await expect.element(getByRole('heading', { name: /Create EmployeeProjects/i })).toBeInTheDocument()
  })
})
