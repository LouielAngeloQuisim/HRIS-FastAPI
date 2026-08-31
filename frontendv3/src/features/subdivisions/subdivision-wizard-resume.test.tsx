import { describe, expect, it, vi } from 'vitest'
import { userEvent } from 'vitest/browser'
import { renderWithClient } from '@/test-utils/providers'
import { SubdivisionWizard } from './components/subdivision-wizard'

const { useCanMock, useSubMock, usePhasesMock, useBlocksMock, useLotsMock, createCatMock, createProjMock } =
  vi.hoisted(() => ({
    useCanMock: vi.fn(), useSubMock: vi.fn(), usePhasesMock: vi.fn(), useBlocksMock: vi.fn(), useLotsMock: vi.fn(),
    createCatMock: vi.fn(), createProjMock: vi.fn(),
  }))

vi.mock('@/context/permissions-provider', () => ({ useCan: (...a: unknown[]) => useCanMock(...a) }))
vi.mock('@/lib/api/subdivisions', () => ({ useSubdivisions: (...a: unknown[]) => useSubMock(...a) }))
vi.mock('@/lib/api/phases', () => ({ usePhases: (...a: unknown[]) => usePhasesMock(...a) }))
vi.mock('@/lib/api/blocks', () => ({ useBlocks: (...a: unknown[]) => useBlocksMock(...a) }))
vi.mock('@/lib/api/lots', () => ({ useLots: (...a: unknown[]) => useLotsMock(...a) }))
vi.mock('@/lib/api/categories', () => ({
  useCreateCategory: () => ({ mutateAsync: createCatMock, isPending: false }),
}))
vi.mock('@/lib/api/projects', () => ({
  useCreateProject: () => ({ mutateAsync: createProjMock, isPending: false }),
}))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

const SUBS = { data: { data: [{ id: 'sub-1', subdivision_code: 'SUB01', name: 'Downtown', description: null, location: '', is_deleted: false, created_at: null }], count: 1 }, isPending: false, isError: false }
const PHASES = { data: { data: [{ id: 'ph-1', code: 'PH1', name: 'Phase 1', subdivision_id: 'sub-1', is_deleted: false, created_at: null }], count: 1 }, isPending: false, isError: false }
const BLOCKS = { data: { data: [{ id: 'blk-1', block_name: 'Block A', phase_id: 'ph-1', is_deleted: false, created_at: null }], count: 1 }, isPending: false, isError: false }
const LOTS = { data: { data: [{ id: 'lot-1', lot_num: 1, lot_name: 'Lot 1', blocks_id: 'blk-1', category_id: null, is_deleted: false, created_at: null }], count: 1 }, isPending: false, isError: false }

describe('Subdivision Wizard resume-after-partial-failure (§8.13)', () => {
  it('Category succeeds, Project fails, Retry re-attempts ONLY Project (no 2nd POST /categories), then completes', async () => {
    useCanMock.mockReturnValue(true)
    useSubMock.mockReturnValue(SUBS)
    usePhasesMock.mockReturnValue(PHASES)
    useBlocksMock.mockReturnValue(BLOCKS)
    useLotsMock.mockReturnValue(LOTS)
    // Category create succeeds (returns id+code); Project create fails first, succeeds on retry.
    createCatMock.mockResolvedValue({ id: 'cat-1', code: 'TestCat' })
    createProjMock.mockRejectedValueOnce({ response: { status: 409, data: { success: false, error: { type: 'conflict', message: 'Project type unavailable', details: [] } } } })
    createProjMock.mockResolvedValueOnce({ id: 'proj-1' })

    const { getByRole, getByPlaceholder, getByText } = await renderWithClient(<SubdivisionWizard />)

    // Step 1: select subdivision, advance.
    await userEvent.click(getByRole('combobox')) // subdivision select trigger
    await userEvent.click(getByRole('option', { name: 'SUB01 - Downtown' }))
    await userEvent.click(getByRole('button', { name: /Next/i }))

    // Step 2: fill category, create -> advances to step 3.
    await userEvent.fill(getByPlaceholder(/category name/i), 'TestCat')
    await userEvent.click(getByRole('button', { name: /Create Category/i }))
    await vi.waitFor(() => { expect(createCatMock).toHaveBeenCalledTimes(1) })

    // Step 3: fill all required project fields.
    await userEvent.fill(getByPlaceholder(/project name/i), 'NewProj')
    const combos = getByRole('combobox').all()
    await userEvent.click(combos[0])                      // project_type
    await userEvent.click(getByRole('option', { name: 'Residential' }))
    await userEvent.click(combos[1])                      // phase
    await userEvent.click(getByRole('option', { name: 'Phase 1' }))
    await userEvent.click(combos[2])                      // block
    await userEvent.click(getByRole('option', { name: 'Block A' }))
    await userEvent.click(combos[3])                      // lot
    await userEvent.click(getByRole('option', { name: 'Lot 1' }))

    // First attempt: project POST fails -> partial-success report appears.
    await userEvent.click(getByRole('button', { name: /^Create Project$/i }))
    await vi.waitFor(() => { expect(createProjMock).toHaveBeenCalledTimes(1) })

    // (a) report names the Category as created.
    await expect.element(getByText(/Category created: TestCat/)).toBeInTheDocument()
    // (b) error surfaced.
    await expect.element(getByText(/Project failed: Project type unavailable/)).toBeInTheDocument()

    // (c) Retry re-attempts ONLY Project — Category POST must NOT fire again.
    await userEvent.click(getByRole('button', { name: /Retry Project/i }))
    await vi.waitFor(() => { expect(createProjMock).toHaveBeenCalledTimes(2) })
    expect(createCatMock).toHaveBeenCalledTimes(1) // still only the original category

    // (d) on project success the wizard completes -> reset to step 1.
    //     Step-1 shows a "Next" button; step 3 ("Create Project") is gone.
    await expect.element(getByRole('button', { name: /^Next$/i })).toBeInTheDocument()
    await expect.element(getByRole('button', { name: /^Create Project$/i })).not.toBeInTheDocument()
  })
})
