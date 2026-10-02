import { test } from '../fixtures'
import { crudJourney } from '../helpers/crud-journey'

test('models create, edit and delete persist through the API', async ({ page, loginAsAdmin }) => {
  await loginAsAdmin()
  const unique = Date.now().toString(36)
  await crudJourney(page, { route: 'models', prefix: 'model', fields: {name: 'E2E ' + unique, description: unique}, editField: 'name', editValue: 'Updated ' + unique })
})
