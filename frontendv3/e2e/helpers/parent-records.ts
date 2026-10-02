import { type Page } from '@playwright/test'
import { createParent } from './crud-journey'

export async function subdivision(page: Page, unique: string) {
  return createParent(page, 'subdivisions', { subdivision_code: 'S' + unique, name: 'Subdivision ' + unique, location: 'Test site' })
}
export async function department(page: Page, unique: string) {
  const division = await createParent(page, 'divisions', { code: 'D' + unique, name: 'Division ' + unique })
  return createParent(page, 'departments', { code: 'D' + unique, name: 'Department ' + unique, division_id: division.id })
}
export async function phase(page: Page, unique: string) {
  const sub = await subdivision(page, unique)
  return createParent(page, 'phases', { code: 'P' + unique, name: 'Phase ' + unique, subdivision_id: sub.id })
}
export async function block(page: Page, unique: string) {
  const parent = await phase(page, unique)
  return createParent(page, 'blocks', { block_name: 'Block ' + unique, phase_id: parent.id })
}
export async function employeeProjectParents(page: Page, unique: string) {
  const sub = await subdivision(page, unique)
  const project = await createParent(page, 'projects', { code: 'P' + unique, name: 'Project ' + unique, subdivision_id: sub.id })
  const employee = await createParent(page, 'employees', { employee_code: 'E' + unique, first_name: 'Employee', last_name: unique, birthdate: '1990-01-01' })
  return { employee, project }
}
