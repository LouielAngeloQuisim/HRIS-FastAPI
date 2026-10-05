import { expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import ProjectsPage from './index'

vi.mock('@/context/permissions-provider', () => ({ useCan: () => true }))
vi.mock('./components/resource-form', () => ({ ResourceForm: () => null }))
vi.mock('./components/resource-delete-dialog', () => ({ ResourceDeleteDialog: () => null }))
vi.mock('@/lib/api/projects', () => ({ useProjects: () => ({ data: { data: [{ id: 'project', code: 'P01', name: 'Named project', subdivision_id: 'subdivision', project_type_id: 'type' }], count: 1 }, isPending: false, isError: false }) }))
vi.mock('@/lib/api/relationship-labels', async importOriginal => ({
  ...await importOriginal<typeof import('@/lib/api/relationship-labels')>(),
  useRelationshipLabels: (resource: string) => ({ data: resource === 'subdivisions' ? { subdivision: 'S01 — Named subdivision' } : { type: 'T01 — Residential' } }),
}))

it('renders readable parent names instead of relationship UUIDs', async () => {
  const screen = await render(<ProjectsPage />)
  await expect.element(screen.getByRole('cell', { name: 'S01 — Named subdivision' })).toBeInTheDocument()
  await expect.element(screen.getByRole('cell', { name: 'T01 — Residential' })).toBeInTheDocument()
})
