import { it, expect, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import { ResourceForm } from './resource-form'
const { mutateAsync } = vi.hoisted(() => ({ mutateAsync: vi.fn().mockResolvedValue({}) }))
vi.mock('@/lib/api/employee-projects', () => ({ useCreateEmployeeProject: () => ({ mutateAsync }), useUpdateEmployeeProject: () => ({ mutateAsync }) }))
vi.mock('@/lib/api/employees', () => ({ useEmployees: () => ({ data: { data: [{ id: 'parent', name: 'Parent', first_name: 'Parent', last_name: 'Employee', task: 'Parent' }] }, isPending: false }) }))
vi.mock('@/lib/api/projects', () => ({ useProjects: () => ({ data: { data: [{ id: 'parent', name: 'Parent', first_name: 'Parent', last_name: 'Employee', task: 'Parent' }] }, isPending: false }) }))
it('submits numeric and false boolean values with selected parents', async () => {
  const onClose = vi.fn()
  const screen = await render(<ResourceForm item={null} open={true} onClose={onClose} />)
  await userEvent.type(screen.getByTestId('employee-project-rendered-hours-input'), '8')
  await userEvent.type(screen.getByTestId('employee-project-assigned-input'), 'false')
  await userEvent.type(screen.getByTestId('employee-project-task-input'), 'Planning')
  await userEvent.click(screen.getByTestId('employee-project-employee-select'))
  await userEvent.click(screen.getByRole('option', { name: 'Parent Employee', exact: true }))
  await userEvent.click(screen.getByTestId('employee-project-project-select'))
  await userEvent.click(screen.getByRole('option', { name: 'Parent', exact: true }))
  await userEvent.click(screen.getByTestId('employee-project-submit-button'))
  expect(mutateAsync).toHaveBeenCalledWith(expect.objectContaining({"employee_id": "parent", "project_id": "parent", "rendered_hours": 8, "is_assigned": false, "task": "Planning"}))
  expect(onClose).toHaveBeenCalledOnce()
})
