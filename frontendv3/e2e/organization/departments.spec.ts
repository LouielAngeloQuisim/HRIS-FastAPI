import { test } from '../fixtures'
import { createParent, crudJourney, selectLabel } from '../helpers/crud-journey'

test('departments preserves associations through create, edit and delete', async ({ page, loginAsAdmin }) => {
  await loginAsAdmin()
  const unique = Date.now().toString(36)
  const parent = await createParent(page, 'divisions', { code: 'D' + unique, name: 'Division ' + unique })
  await crudJourney(page, { route: 'departments', prefix: 'department', fields: { code: unique, name: 'Department ' + unique }, editField: 'name', editValue: 'Updated ' + unique, expected: { division_id: parent.id }, prepare: async () => { await selectLabel(page, 'department-division-select', parent.name) } })
})
