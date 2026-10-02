import { test } from '../fixtures'
import { createParent, crudJourney, selectLabel } from '../helpers/crud-journey'
import { employeeProjectParents } from '../helpers/parent-records'

test('emp-tasks preserves associations through create, edit and delete', async ({ page, loginAsAdmin }) => {
  await loginAsAdmin()
  const unique = Date.now().toString(36)
  const { employee, project } = await employeeProjectParents(page, unique); const parent = await createParent(page, 'employee-projects', { employee_id: employee.id, project_id: project.id, task: 'Parent task ' + unique })
  await crudJourney(page, { route: 'emp-tasks', prefix: 'emp-task', fields: { 'task-desc': 'Task ' + unique, 'rendered-hours': '8', 'assigned-hours': '10', approved: 'false', adjusted: 'true' }, editField: 'task-desc', editValue: 'Updated ' + unique, expected: { emp_project_id: parent.id, rendered_hours: 8, assigned_hours: '10.00', approved: false, is_adjusted: true }, prepare: async () => { await selectLabel(page, 'emp-task-employee-project-select', parent.task) } })
})
