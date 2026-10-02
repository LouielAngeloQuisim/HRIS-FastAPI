import { test } from '../fixtures'
import {  crudJourney, selectLabel } from '../helpers/crud-journey'
import { employeeProjectParents } from '../helpers/parent-records'

test('employee-projects preserves associations through create, edit and delete', async ({ page, loginAsAdmin }) => {
  await loginAsAdmin()
  const unique = Date.now().toString(36)
  const { employee, project } = await employeeProjectParents(page, unique)
  await crudJourney(page, { route: 'employee-projects', prefix: 'employee-project', fields: { task: 'Task ' + unique, 'rendered-hours': '8', assigned: 'true' }, editField: 'task', editValue: 'Updated ' + unique, expected: { employee_id: employee.id, project_id: project.id, rendered_hours: 8, is_assigned: true }, prepare: async () => { await selectLabel(page, 'employee-project-employee-select', employee.first_name + ' ' + employee.last_name); await selectLabel(page, 'employee-project-project-select', project.name) } })
})
