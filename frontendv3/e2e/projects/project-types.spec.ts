import { test } from '../fixtures'
import { crudJourney } from '../helpers/crud-journey'

test('project-types create, edit and delete persist through the API', async ({ page, loginAsAdmin }) => {
  await loginAsAdmin()
  const unique = Date.now().toString(36)
  await crudJourney(page, { route: 'project-types', prefix: 'project-type', fields: {code: unique, name: 'E2E ' + unique, description: unique}, editField: 'name', editValue: 'Updated ' + unique })
})
