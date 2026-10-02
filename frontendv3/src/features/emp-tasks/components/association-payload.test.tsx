import { it, expect, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import { ResourceForm } from './resource-form'
const { mutateAsync } = vi.hoisted(() => ({ mutateAsync: vi.fn().mockResolvedValue({}) }))
vi.mock('@/lib/api/emp-tasks', () => ({ useCreateEmpTask: () => ({ mutateAsync }), useUpdateEmpTask: () => ({ mutateAsync }) }))
vi.mock('@/lib/api/employee-projects', () => ({ useEmployeeProjects: () => ({ data: { data: [{ id: 'parent', name: 'Parent', first_name: 'Parent', last_name: 'Employee', task: 'Parent' }] }, isPending: false }) }))
it('submits numeric and false boolean values with selected parents', async () => {
  const onClose = vi.fn()
  const screen = await render(<ResourceForm item={null} open={true} onClose={onClose} />)
  await userEvent.type(screen.getByTestId('emp-task-rendered-hours-input'), '8')
  await userEvent.type(screen.getByTestId('emp-task-assigned-hours-input'), '10.5')
  await userEvent.type(screen.getByTestId('emp-task-approved-input'), 'false')
  await userEvent.type(screen.getByTestId('emp-task-adjusted-input'), 'true')
  await userEvent.type(screen.getByTestId('emp-task-task-desc-input'), 'Planning')
  await userEvent.click(screen.getByTestId('emp-task-employee-project-select'))
  await userEvent.click(screen.getByRole('option', { name: 'Parent', exact: true }))
  await userEvent.click(screen.getByTestId('emp-task-submit-button'))
  expect(mutateAsync).toHaveBeenCalledWith(expect.objectContaining({"emp_project_id": "parent", "rendered_hours": 8, "assigned_hours": 10.5, "approved": false, "is_adjusted": true, "task_desc": "Planning"}))
  expect(onClose).toHaveBeenCalledOnce()
})
