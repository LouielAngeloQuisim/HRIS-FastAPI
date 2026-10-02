import { test } from '../fixtures'
import { crudJourney, createParent, selectLabel } from '../helpers/crud-journey'

test('models create, edit and delete persist through the API', async ({ page, loginAsAdmin }) => {
  await loginAsAdmin()
  const unique = Date.now().toString(36)
  const parent = await createParent(page, 'model-types', { code: 'M' + unique, name: 'Type ' + unique })
  await crudJourney(page, { route: 'models', prefix: 'model', fields: {name: 'E2E ' + unique}, editField: 'name', editValue: 'Updated ' + unique, expected: { model_type_id: parent.id }, prepare: async () => { await selectLabel(page, 'model-model-type-select', parent.name) } })
})
