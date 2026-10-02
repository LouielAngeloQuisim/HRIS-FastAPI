import { test } from '../fixtures'
import {  crudJourney, selectLabel } from '../helpers/crud-journey'
import { subdivision } from '../helpers/parent-records'

test('phases preserves associations through create, edit and delete', async ({ page, loginAsAdmin }) => {
  await loginAsAdmin()
  const unique = Date.now().toString(36)
  const parent = await subdivision(page, unique)
  await crudJourney(page, { route: 'phases', prefix: 'phase', fields: { code: unique, name: 'Phase ' + unique }, editField: 'name', editValue: 'Updated ' + unique, expected: { subdivision_id: parent.id }, prepare: async () => { await selectLabel(page, 'phase-subdivision-select', parent.name) } })
})
