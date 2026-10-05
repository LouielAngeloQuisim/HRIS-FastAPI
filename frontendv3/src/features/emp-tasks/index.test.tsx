import { expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import EmpTaskPage from './index'

vi.mock('@/context/permissions-provider', () => ({ useCan: () => true }))
vi.mock('./components/resource-form', () => ({ ResourceForm: () => null }))
vi.mock('./components/resource-delete-dialog', () => ({ ResourceDeleteDialog: () => null }))
vi.mock('@/lib/api/emp-tasks', () => ({ useEmpTasks: () => ({ data: { data: [{ id: 'task', emp_project_id: 'assignment', task_desc: 'Fixture task' }], count: 1 }, isPending: false, isError: false }) }))
vi.mock('@/lib/api/relationship-labels', async () => ({
  ...await import('@/lib/api/relationship-label-text'),
  useRelationshipLabels: () => ({ data: { assignment: 'EMP01 — Named Employee → P01 — Named Project' } }),
}))

it('renders the task assignment with employee and project labels', async () => {
  const screen = await render(<EmpTaskPage />)
  await expect.element(screen.getByRole('cell', { name: 'EMP01 — Named Employee → P01 — Named Project' })).toBeInTheDocument()
})
