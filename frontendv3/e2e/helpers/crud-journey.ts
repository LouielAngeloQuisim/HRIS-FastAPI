import { expect, type Page, type Response } from '@playwright/test'

export const apiUrl = process.env.E2E_API_URL || 'http://127.0.0.1:8000/api/v1'

export async function createParent(page: Page, resource: string, data: Record<string, unknown>) {
  const token = (await page.context().cookies()).find(c => c.name === 'hris_at')?.value
  if (!token) throw new Error('Missing authenticated test session')
  const response = await page.request.post(apiUrl + '/' + resource, {
    headers: { Authorization: 'Bearer ' + token }, data,
  })
  expect(response.status(), 'Create prerequisite ' + resource).toBe(201)
  const body = await response.json()
  return body.data || body
}

export async function selectLabel(page: Page, testId: string, label: string) {
  await page.getByTestId(testId).click()
  await page.getByRole('option', { name: label, exact: true }).click()
}

export function waitForWrite(page: Page, resource: string, method: string, id?: string) {
  const path = new URL(apiUrl + '/' + resource + (id ? '/' + id : '')).pathname
  return page.waitForResponse(r =>
    r.status() !== 307 && r.request().method() === method && new URL(r.url()).pathname.replace(/\/$/, '') === path
  )
}

export async function assertWrite(response: Response, status: number) {
  expect(response.status(), response.request().method() + ' ' + new URL(response.url()).pathname).toBe(status)
  const body = await response.json()
  return body.data || body
}

export async function crudJourney(page: Page, config: {
  route: string; prefix: string; add?: string; resource?: string;
  fields: Record<string, string>; editField: string; editValue: string;
  prepare?: () => Promise<void>; expected?: Record<string, unknown>; readList?: boolean;
}) {
  const { route, prefix, fields, editField, editValue } = config
  const resource = config.resource || route
  await page.goto('/' + route)
  await expect(page.getByTestId(config.add || 'add-' + prefix + '-button')).toBeVisible()
  await page.getByTestId(config.add || 'add-' + prefix + '-button').click()
  for (const [field, value] of Object.entries(fields)) await page.getByTestId(prefix + '-' + field + '-input').fill(value)
  if (config.prepare) await config.prepare()
  const creating = waitForWrite(page, resource, 'POST')
  await page.getByTestId(prefix + '-submit-button').click()
  const created = await assertWrite(await creating, 201)
  expect(created.id).toBeTruthy()
  if (config.expected) expect(created).toMatchObject(config.expected)
  await expect(page.getByTestId(prefix + '-submit-button')).not.toBeVisible()
  await page.getByTestId('edit-' + prefix + '-button-' + created.id).click()
  await page.getByTestId(prefix + '-' + editField + '-input').fill(editValue)
  const updating = waitForWrite(page, resource, 'PATCH', created.id)
  await page.getByTestId(prefix + '-submit-button').click()
  await assertWrite(await updating, 200)
  await expect(page.getByTestId(prefix + '-submit-button')).not.toBeVisible()
  const token = (await page.context().cookies()).find(c => c.name === 'hris_at')!.value
  const persisted = await page.request.get(apiUrl + '/' + resource + (config.readList ? '/?limit=100' : '/' + created.id), { headers: { Authorization: 'Bearer ' + token } })
  expect(persisted.status()).toBe(200)
  const savedBody = await persisted.json()
  const saved = config.readList ? savedBody.data.find((row: { id: string }) => row.id === created.id) : (savedBody.data || savedBody)
  expect(saved).toBeTruthy()
  expect(JSON.stringify(saved)).toContain(editValue)
  const unchanged = Object.fromEntries(Object.entries(config.expected || {}).filter(([key]) => !['name', 'title', 'block_name', 'lot_name', 'task', 'task_desc'].includes(key)))
  expect(saved).toMatchObject(unchanged)
  await page.getByTestId('delete-' + prefix + '-button-' + created.id).click()
  const deleting = waitForWrite(page, resource, 'DELETE', created.id)
  await page.getByRole('button', { name: 'Delete', exact: true }).last().click()
  await assertWrite(await deleting, 200)
  await expect(page.getByTestId('edit-' + prefix + '-button-' + created.id)).toHaveCount(0)
}
