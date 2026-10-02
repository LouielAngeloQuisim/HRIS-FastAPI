import { test } from '../fixtures'
import {  crudJourney, selectLabel } from '../helpers/crud-journey'
import { department } from '../helpers/parent-records'

test('positions preserves associations through create, edit and delete', async ({ page, loginAsAdmin }) => {
  await loginAsAdmin()
  const unique = Date.now().toString(36)
  const parent = await department(page, unique)
  await crudJourney(page, { route: 'positions', prefix: 'position', fields: { code: unique, title: 'Position ' + unique }, editField: 'title', editValue: 'Updated ' + unique, expected: { department_id: parent.id }, prepare: async () => { await selectLabel(page, 'position-department-select', parent.name) } })
})
