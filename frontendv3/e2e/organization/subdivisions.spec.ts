import { test } from '../fixtures'
import { crudJourney } from '../helpers/crud-journey'

test('subdivisions create, edit and delete persist through the API', async ({ page, loginAsAdmin }) => {
  await loginAsAdmin()
  const unique = Date.now().toString(36)
  await crudJourney(page, { route: 'subdivisions', prefix: 'subdivision', fields: {code: unique, name: 'E2E ' + unique, location: unique}, editField: 'name', editValue: 'Updated ' + unique })
})
