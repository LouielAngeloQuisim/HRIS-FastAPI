import { describe, expect, it } from 'vitest'
import { render } from 'vitest-browser-react'
import { DashboardTiles, DashboardTilesSkeleton } from './dashboard-tiles'
import { type DashboardStats } from '@/lib/api/types'

const tiles = [
  { key: 'employee_records', label: 'Employee Records' },
  { key: 'divisions', label: 'Divisions' },
  { key: 'departments', label: 'Departments' },
  { key: 'projects', label: 'Projects' },
  { key: 'subdivisions', label: 'Subdivisions' },
  { key: 'owners', label: 'Owners' },
  { key: 'employee_projects', label: 'Employee Projects' },
  { key: 'model_count', label: 'Model Count' },
  { key: 'dtr_records_daily_count', label: 'Daily Time Records' },
] as const

describe('DashboardTiles', () => {
  const data: DashboardStats = {
    employee_records: 42,
    divisions: 3,
    departments: 7,
    projects: 12,
    subdivisions: 5,
    owners: 8,
    employee_projects: 15,
    model_count: 4,
    dtr_records_daily_count: 0,
  }

  it('renders all 9 KPI tiles verbatim from backend (including dtr=0)', async () => {
    const screen = await render(<DashboardTiles data={data} />)

    for (const tile of tiles) {
      const el = await screen.getByTestId(`kpi-${tile.key}`)
      await expect.element(el).toBeInTheDocument()
      await expect.element(el).toHaveTextContent(data[tile.key].toLocaleString())
    }
  })

  it('shows the DTR hint when dtr_records_daily_count is 0', async () => {
    const screen = await render(<DashboardTiles data={data} />)
    await expect
      .element(screen.getByText(/Attendance tracking not live yet/i))
      .toBeInTheDocument()
  })

  it('renders skeleton cards while loading (smoke test)', async () => {
    const screen = await render(<DashboardTilesSkeleton />)
    const cards = screen.container.querySelectorAll('[data-slot="card"]')
    expect(cards.length).toBe(9)
  })
})
