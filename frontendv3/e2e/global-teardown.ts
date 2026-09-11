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

export default async function globalTeardown(_config: FullConfig) {
  console.log('Global teardown: cleaning up seeded test data...')
  try {
    let state: SeedState = { divisionIds: [], departmentIds: [], subdivisionIds: [] }
    if (fs.existsSync(STATE_FILE)) {
      try {
        state = JSON.parse(fs.readFileSync(STATE_FILE, 'utf-8'))
      } catch {
        // ignore parse errors
      }
    }

    for (const id of state.divisionIds) {
      await fetch(`${API_URL}/divisions/${id}`, { method: 'DELETE' }).catch(() => {})
    }
    for (const id of state.departmentIds) {
      await fetch(`${API_URL}/departments/${id}`, { method: 'DELETE' }).catch(() => {})
    }
    for (const id of state.subdivisionIds) {
      await fetch(`${API_URL}/subdivisions/${id}`, { method: 'DELETE' }).catch(() => {})
    }

    try {
      fs.unlinkSync(STATE_FILE)
    } catch {
      // ignore
    }
    console.log('Global teardown: cleanup complete')
  } catch (err) {
    console.error('Global teardown failed:', err)
  }
}
