import { type FullConfig } from '@playwright/test'
import * as fs from 'fs'
import * as path from 'path'

const API_URL = process.env.E2E_API_URL || 'http://localhost:8000/api/v1'
const STATE_FILE = path.join(process.cwd(), 'e2e', '.e2e-seed-state.json')

interface SeedState {
  divisionIds: string[]
  departmentIds: string[]
  subdivisionIds: string[]
}

async function seedDivisions(): Promise<string[]> {
  const ids: string[] = []
  for (let i = 0; i < 3; i++) {
    const res = await fetch(`${API_URL}/divisions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        code: `E2E-DIV-${Date.now()}-${i}`,
        name: `E2E Division ${i}`,
        description: 'Seeded for E2E tests',
      }),
    })
    if (res.ok) {
      const body = await res.json()
      ids.push(body.data?.id || body.id)
    }
  }
  return ids
}

async function seedDepartments(divisionId: string): Promise<string[]> {
  const ids: string[] = []
  for (let i = 0; i < 2; i++) {
    const res = await fetch(`${API_URL}/departments`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        code: `E2E-DEPT-${Date.now()}-${i}`,
        name: `E2E Department ${i}`,
        division_id: divisionId,
      }),
    })
    if (res.ok) {
      const body = await res.json()
      ids.push(body.data?.id || body.id)
    }
  }
  return ids
}

async function seedSubdivisions(departmentId: string): Promise<string[]> {
  const ids: string[] = []
  for (let i = 0; i < 2; i++) {
    const res = await fetch(`${API_URL}/subdivisions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        code: `E2E-SUB-${Date.now()}-${i}`,
        name: `E2E Subdivision ${i}`,
        department_id: departmentId,
      }),
    })
    if (res.ok) {
      const body = await res.json()
      ids.push(body.data?.id || body.id)
    }
  }
  return ids
}

export default async function globalSetup(_config: FullConfig) {
  console.log('Global setup: seeding test data...')
  try {
    const divisionIds = await seedDivisions()
    let departmentIds: string[] = []
    let subdivisionIds: string[] = []

    if (divisionIds.length > 0) {
      departmentIds = await seedDepartments(divisionIds[0])
      if (departmentIds.length > 0) {
        subdivisionIds = await seedSubdivisions(departmentIds[0])
      }
    }

    const state: SeedState = { divisionIds, departmentIds, subdivisionIds }
    fs.mkdirSync(path.dirname(STATE_FILE), { recursive: true })
    fs.writeFileSync(STATE_FILE, JSON.stringify(state))
    console.log('Global setup: seed complete')
  } catch (err) {
    console.error('Global setup failed:', err)
  }
}
