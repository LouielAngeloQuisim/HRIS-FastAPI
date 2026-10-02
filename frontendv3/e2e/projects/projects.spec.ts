import { test } from '../fixtures'
import { createParent, crudJourney, selectLabel } from '../helpers/crud-journey'
import { subdivision } from '../helpers/parent-records'

test('projects preserves associations through create, edit and delete', async ({ page, loginAsAdmin }) => {
  await loginAsAdmin()
  const unique = Date.now().toString(36)
  const parent = await subdivision(page, unique); const type = await createParent(page, 'project-types', { code: 'T' + unique, name: 'Type ' + unique })
  await crudJourney(page, { route: 'projects', prefix: 'project', fields: { code: unique, name: 'Project ' + unique }, editField: 'name', editValue: 'Updated ' + unique, expected: { subdivision_id: parent.id, project_type_id: type.id }, prepare: async () => { await selectLabel(page, 'project-subdivision-select', parent.name); await selectLabel(page, 'project-type-select', type.name) } })
})
