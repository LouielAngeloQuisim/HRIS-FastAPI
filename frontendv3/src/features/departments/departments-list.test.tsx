import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import DepartmentPage from './index'

vi.mock('./components/resource-form', () => ({ ResourceForm: () => null }))
vi.mock('./components/resource-delete-dialog', () => ({ ResourceDeleteDialog: () => null }))

const { useDepartmentsMock } = vi.hoisted(() => ({ useDepartmentsMock: vi.fn() }))
vi.mock('@/lib/api/departments', () => ({
  useDepartments: (...args: unknown[]) => useDepartmentsMock(...args),
}))
const { useCanMock } = vi.hoisted(() => ({ useCanMock: vi.fn() }))
vi.mock('@/context/permissions-provider', () => ({ useCan: (...args: unknown[]) => useCanMock(...args) }))

const DEPTS = {
  data: [
    { id: 'd1', code: 'HR', name: 'Human Resources', description: 'd', division_id: 'v1', manager_id: 'u1' },
  ],
  count: 1,
}

describe('Departments list (§8.1 template / §8.6 permission gate)', () => {
  it('renders rows bound to useDepartments data', async () => {
    useDepartmentsMock.mockReturnValue({ data: DEPTS, isPending: false, isError: false, refetch: vi.fn() })
    useCanMock.mockReturnValue(true)
    const { getByText } = await render(<DepartmentPage />)
    await expect.element(getByText('HR')).toBeInTheDocument()
    await expect.element(getByText('Human Resources')).toBeInTheDocument()
  })

  it('hides the Add button when create permission is denied', async () => {
    useDepartmentsMock.mockReturnValue({ data: DEPTS, isPending: false, isError: false, refetch: vi.fn() })
    useCanMock.mockImplementation((_m: string, action: string) => action === 'view')
    const denied = await render(<DepartmentPage />)
    await expect.element(denied.getByRole('button', { name: /Add Department/i })).not.toBeInTheDocument()

    useCanMock.mockReturnValue(true)
    const allowed = await render(<DepartmentPage />)
    await expect.element(allowed.getByRole('button', { name: /Add Department/i })).toBeInTheDocument()
  })
})
