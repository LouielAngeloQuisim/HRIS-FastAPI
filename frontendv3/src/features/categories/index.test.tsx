import { expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import CategoryPage from './index'

vi.mock('@/context/permissions-provider', () => ({ useCan: () => true }))
vi.mock('./components/resource-form', () => ({ ResourceForm: () => null }))
vi.mock('./components/resource-delete-dialog', () => ({ ResourceDeleteDialog: () => null }))
vi.mock('@/lib/api/categories', () => ({ useCategories: () => ({ data: { data: [{ id: 'category', code: 'C01', project_id: 'project', model_id: 'model', phase_id: 'phase', blocks_id: 'block', owner_id: 'owner', lot_id: 'lot' }], count: 1 }, isPending: false, isError: false }) }))
vi.mock('@/lib/api/relationship-labels', async () => ({
  ...await import('@/lib/api/relationship-label-text'),
  useRelationshipLabels: () => ({ data: { project: 'P01 — Project', model: 'Model A', phase: 'Phase 1', block: 'Block 2', owner: 'Readable Owner', lot: 'Lot 3' } }),
}))

it('renders every category parent as a readable label', async () => {
  const screen = await render(<CategoryPage />)
  for (const name of ['P01 — Project', 'Model A', 'Phase 1', 'Block 2', 'Readable Owner', 'Lot 3']) {
    await expect.element(screen.getByRole('cell', { name, exact: true })).toBeInTheDocument()
  }
})
