import { test } from '../fixtures'
import { crudJourney } from '../helpers/crud-journey'

test('shift create, edit and delete persist', async ({ page, loginAsAdmin }) => {
  await loginAsAdmin()
  const unique = Date.now().toString(36)
  await crudJourney(page, { route: 'shifts', prefix: 'shift', fields: {
    code: unique, name: 'Shift ' + unique, 'start-time': '08:00', 'end-time': '17:00',
  }, editField: 'name', editValue: 'Updated ' + unique })
})
