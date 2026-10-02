import { test } from '../fixtures'
import { crudJourney } from '../helpers/crud-journey'

test('owners create, edit and delete persist through the API', async ({ page, loginAsAdmin }) => {
  await loginAsAdmin()
  const unique = Date.now().toString(36)
  await crudJourney(page, { route: 'owners', prefix: 'owner', fields: {name: 'E2E ' + unique, email: 'e2e@example.com', phone: '5551234'}, editField: 'name', editValue: 'Updated ' + unique })
})
