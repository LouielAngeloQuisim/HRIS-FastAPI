import { beforeEach, describe, expect, it, vi } from 'vitest'
import { userEvent } from 'vitest/browser'
import { renderWithClient } from '@/test-utils/providers'
import { SubdivisionWizard } from './components/subdivision-wizard'

const { createCat, createProject } = vi.hoisted(() => ({ createCat: vi.fn(), createProject: vi.fn() }))
vi.mock('@/context/permissions-provider', () => ({ useCan: () => true }))
vi.mock('@/lib/api/subdivisions', () => ({ useSubdivisions: () => ({ data: { data: [{ id: 'sub-1', subdivision_code: 'SUB01', name: 'Downtown' }] } }) }))
vi.mock('@/lib/api/phases', () => ({ usePhases: () => ({ data: { data: [{ id: 'ph-1', name: 'Phase 1', subdivision_id: 'sub-1' }] } }) }))
vi.mock('@/lib/api/blocks', () => ({ useBlocks: () => ({ data: { data: [{ id: 'blk-1', block_name: 'Block A', phase_id: 'ph-1' }] } }) }))
vi.mock('@/lib/api/lots', () => ({ useLots: () => ({ data: { data: [{ id: 'lot-1', lot_name: 'Lot 1', blocks_id: 'blk-1' }] } }) }))
vi.mock('@/lib/api/project-types', () => ({ useProjectTypes: () => ({ data: { data: [{ id: 'pt-1', name: 'Residential' }] } }) }))
vi.mock('@/lib/api/categories', () => ({ useCreateCategory: () => ({ mutateAsync: createCat, isPending: false }) }))
vi.mock('@/lib/api/projects', () => ({ useCreateProject: () => ({ mutateAsync: createProject, isPending: false }) }))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

async function fillWizard() {
  const screen = await renderWithClient(<SubdivisionWizard />)
  await userEvent.click(screen.getByRole('combobox'))
  await userEvent.click(screen.getByRole('option', { name: 'SUB01 - Downtown' }))
  await userEvent.click(screen.getByRole('button', { name: /^Next$/ }))
  await userEvent.fill(screen.getByPlaceholder('Enter category name'), 'TestCat')
  await userEvent.click(screen.getByRole('button', { name: /^Next$/ }))
  expect(createCat).not.toHaveBeenCalled()
  expect(createProject).not.toHaveBeenCalled()
  await userEvent.fill(screen.getByPlaceholder('Enter project code'), 'PROJ01')
  await userEvent.fill(screen.getByPlaceholder('Enter project name'), 'NewProj')
  const combos = screen.getByRole('combobox').all()
  for (const [index, label] of ['Residential', 'Phase 1', 'Block A', 'Lot 1'].entries()) {
    await userEvent.click(combos[index])
    await userEvent.click(screen.getByRole('option', { name: label, exact: true }))
  }
  return screen
}
describe('Subdivision wizard dependency order and partial failure', () => {
  beforeEach(() => { createCat.mockReset(); createProject.mockReset() })
  it('creates the project first and retries a failed category without duplicating the project', async () => {
    createProject.mockResolvedValue({ id: 'proj-1', name: 'NewProj' })
    createCat.mockRejectedValueOnce({ response: { data: { error: { message: 'Category code already exists' } } } }).mockResolvedValueOnce({ id: 'cat-1' })
    const screen = await fillWizard()
    await userEvent.click(screen.getByRole('button', { name: 'Create Project & Category', exact: true }))
    await expect.element(screen.getByRole('alert')).toHaveTextContent('Project created: NewProj')
    await expect.element(screen.getByRole('alert')).toHaveTextContent('Category code already exists')
    expect(createProject).toHaveBeenCalledExactlyOnceWith({ code: 'PROJ01', name: 'NewProj', description: '', project_type_id: 'pt-1', subdivision_id: 'sub-1' })
    expect(createCat).toHaveBeenCalledExactlyOnceWith({ code: 'TestCat', description: '', project_id: 'proj-1', phase_id: 'ph-1', blocks_id: 'blk-1', lot_id: 'lot-1' })
    await userEvent.click(screen.getByRole('button', { name: 'Retry Category', exact: true }))
    await expect.element(screen.getByRole('button', { name: /^Next$/ })).toBeVisible()
    expect(createProject).toHaveBeenCalledTimes(1)
    expect(createCat).toHaveBeenCalledTimes(2)
    expect(createCat.mock.invocationCallOrder[0]).toBeGreaterThan(createProject.mock.invocationCallOrder[0])
  })
  it('does not create a category if project creation fails', async () => {
    createProject.mockRejectedValue({ response: { data: { error: { message: 'Project code already exists' } } } })
    const screen = await fillWizard()
    await userEvent.click(screen.getByRole('button', { name: 'Create Project & Category', exact: true }))
    await expect.element(screen.getByRole('alert')).toHaveTextContent('Project code already exists')
    expect(createCat).not.toHaveBeenCalled()
  })
})
