import { test } from '../fixtures'
import { crudJourney } from '../helpers/crud-journey'

test('model-types create, edit and delete persist through the API', async ({ page, loginAsAdmin }) => {
  await loginAsAdmin()
  const unique = Date.now().toString(36)
  await crudJourney(page, { route: 'model-types', prefix: 'model-type', fields: {code: unique, name: 'E2E ' + unique}, editField: 'name', editValue: 'Updated ' + unique })
})
