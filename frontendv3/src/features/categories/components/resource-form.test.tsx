import { beforeEach, expect, it, vi } from 'vitest'
import { userEvent } from 'vitest/browser'
import { render } from 'vitest-browser-react'
import { ResourceForm } from './resource-form'
const { create } = vi.hoisted(() => ({ create: vi.fn() }))
vi.mock('@/lib/api/categories', () => ({ useCreateCategory: () => ({ mutateAsync: create, isPending: false }), useUpdateCategory: () => ({ mutateAsync: create, isPending: false }) }))
vi.mock('@/lib/api/projects', () => ({ useProjects: () => ({ data: { data: [{ id: 'project-1', name: 'Project', subdivision_id: 'sub-1' }] }, isPending: false }) }))
vi.mock('@/lib/api/phases', () => ({ usePhases: () => ({ data: { data: [{ id: 'phase-1', name: 'Phase', subdivision_id: 'sub-1' }, { id: 'other-phase', name: 'Other subdivision phase', subdivision_id: 'sub-2' }] }, isPending: false }) }))
vi.mock('@/lib/api/blocks', () => ({ useBlocks: () => ({ data: { data: [{ id: 'block-1', block_name: 'Block', phase_id: 'phase-1' }] }, isPending: false }) }))
vi.mock('@/lib/api/lots', () => ({ useLots: () => ({ data: { data: [{ id: 'lot-1', lot_name: 'Lot', blocks_id: 'block-1' }] }, isPending: false }) }))
vi.mock('@/lib/api/models', () => ({ useModels: () => ({ data: { data: [{ id: 'model-1', name: 'Model' }] }, isPending: false }) }))
vi.mock('@/lib/api/owners', () => ({ useOwners: () => ({ data: { data: [{ id: 'owner-1', first_name: 'Test', last_name: 'Owner' }] }, isPending: false }) }))
beforeEach(() => { create.mockReset() })
async function fill(screen: Awaited<ReturnType<typeof render>>) {
  await userEvent.fill(screen.getByLabelText('Code', { exact: true }), 'CAT1')
  for (const [label, option] of [['Project', 'Project'], ['Phase', 'Phase'], ['Block', 'Block'], ['Lot', 'Lot'], ['Model', 'Model'], ['Owner', 'Test Owner']]) {
    await userEvent.click(screen.getByRole('combobox', { name: label, exact: true }))
    if (label === 'Phase') await expect.element(screen.getByRole('option', { name: 'Other subdivision phase', exact: true })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('option', { name: option, exact: true }))
  }
}
it('saves category code and every selected relationship with typed overhead', async () => {
  create.mockResolvedValue({ id: 'cat-1' })
  const close = vi.fn()
  const screen = await render(<ResourceForm item={null} open onClose={close} />)
  await fill(screen)
  await userEvent.click(screen.getByRole('switch', { name: 'Overhead', exact: true }))
  await userEvent.click(screen.getByRole('button', { name: 'Create', exact: true }))
  await vi.waitFor(() => expect(create).toHaveBeenCalledExactlyOnceWith({ code: 'CAT1', description: '', location: '', is_overhead: true, project_id: 'project-1', phase_id: 'phase-1', blocks_id: 'block-1', lot_id: 'lot-1', model_id: 'model-1', owner_id: 'owner-1' }))
  expect(close).toHaveBeenCalledOnce()
})
it('keeps the form open and displays the backend error when saving fails', async () => {
  create.mockRejectedValue({ response: { data: { error: { message: 'Category code already exists' } } } })
  const close = vi.fn()
  const screen = await render(<ResourceForm item={null} open onClose={close} />)
  await fill(screen)
  await userEvent.click(screen.getByRole('button', { name: 'Create', exact: true }))
  await expect.element(screen.getByRole('alert')).toHaveTextContent('Category code already exists')
  expect(close).not.toHaveBeenCalled()
})
it('requires project and phase before submitting', async () => {
  const screen = await render(<ResourceForm item={null} open onClose={vi.fn()} />)
  await userEvent.fill(screen.getByLabelText('Code', { exact: true }), 'CAT1')
  await userEvent.click(screen.getByRole('button', { name: 'Create', exact: true }))
  await expect.element(screen.getByText('Select a project', { exact: true })).toBeVisible()
  await expect.element(screen.getByText('Select a phase', { exact: true })).toBeVisible()
  expect(create).not.toHaveBeenCalled()
})
