import { test } from '../fixtures'
import {  crudJourney, selectLabel } from '../helpers/crud-journey'
import { phase } from '../helpers/parent-records'

test('blocks preserves associations through create, edit and delete', async ({ page, loginAsAdmin }) => {
  await loginAsAdmin()
  const unique = Date.now().toString(36)
  const parent = await phase(page, unique)
  await crudJourney(page, { route: 'blocks', prefix: 'blocks', fields: { name: 'Block ' + unique }, editField: 'name', editValue: 'Updated ' + unique, expected: { phase_id: parent.id, block_name: 'Block ' + unique }, prepare: async () => { await selectLabel(page, 'blocks-phase-select', parent.name) } })
})
