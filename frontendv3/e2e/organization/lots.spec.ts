import { test } from '../fixtures'
import {  crudJourney, selectLabel } from '../helpers/crud-journey'
import { block } from '../helpers/parent-records'

test('lots preserves associations through create, edit and delete', async ({ page, loginAsAdmin }) => {
  await loginAsAdmin()
  const unique = Date.now().toString(36)
  const parent = await block(page, unique)
  await crudJourney(page, { route: 'lots', prefix: 'lots', fields: { 'lot-number': 'Lot ' + unique, 'numeric-number': '101' }, editField: 'lot-number', editValue: 'Updated ' + unique, expected: { blocks_id: parent.id, lot_name: 'Lot ' + unique, lot_num: 101 }, prepare: async () => { await selectLabel(page, 'lots-block-select', parent.block_name) } })
})
