import { test } from '../fixtures'
import { crudJourney, selectLabel } from '../helpers/crud-journey'

test('holiday configuration create, edit and delete persist', async ({ page, loginAsAdmin }) => {
  await loginAsAdmin()
  const unique = Date.now().toString(36)
  await crudJourney(page, {
    route: 'holidays', readList: true, prefix: 'holiday', add: 'holiday-add-button',
    fields: { code: unique, name: 'Holiday ' + unique, 'month-day': '12-25', region: 'NCR' },
    editField: 'name', editValue: 'Updated ' + unique,
    expected: { type: 'special_non_working', month_day: '12-25', region_code: 'NCR' },
    prepare: async () => { await selectLabel(page, 'holiday-type-select', 'Special Non-working') },
  })
})
