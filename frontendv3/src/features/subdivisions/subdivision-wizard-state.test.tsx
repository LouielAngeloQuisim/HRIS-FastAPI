import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import { SubdivisionWizard } from './components/subdivision-wizard'

const { useCanMock, useSubMock, usePhasesMock, useBlocksMock, useLotsMock, createCatMock, createProjMock } =
  vi.hoisted(() => ({
    useCanMock: vi.fn(),
    useSubMock: vi.fn(),
    usePhasesMock: vi.fn(),
    useBlocksMock: vi.fn(),
    useLotsMock: vi.fn(),
    createCatMock: vi.fn(),
    createProjMock: vi.fn(),
  }))

vi.mock('@/context/permissions-provider', () => ({ useCan: (...a: unknown[]) => useCanMock(...a) }))
vi.mock('@/lib/api/subdivisions', () => ({ useSubdivisions: (...a: unknown[]) => useSubMock(...a) }))
vi.mock('@/lib/api/phases', () => ({ usePhases: (...a: unknown[]) => usePhasesMock(...a) }))
vi.mock('@/lib/api/blocks', () => ({ useBlocks: (...a: unknown[]) => useBlocksMock(...a) }))
vi.mock('@/lib/api/lots', () => ({ useLots: (...a: unknown[]) => useLotsMock(...a) }))
vi.mock('@/lib/api/categories', () => ({ useCreateCategory: () => ({ mutateAsync: createCatMock, isPending: false }) }))
vi.mock('@/lib/api/projects', () => ({ useCreateProject: () => ({ mutateAsync: createProjMock, isPending: false }) }))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

describe('Subdivision Wizard state-preservation (§8.5)', () => {
  it('retains step-2 values when navigating Back then Next again', async () => {
    useCanMock.mockReturnValue(true)
    useSubMock.mockReturnValue({ data: { data: [{ id: 'sub-1', subdivision_code: 'SUB01', name: 'Downtown', description: null, location: '', is_deleted: false, created_at: null }], count: 1 }, isPending: false, isError: false })
    usePhasesMock.mockReturnValue({ data: { data: [], count: 0 }, isPending: false, isError: false })
    useBlocksMock.mockReturnValue({ data: { data: [], count: 0 }, isPending: false, isError: false })
    useLotsMock.mockReturnValue({ data: { data: [], count: 0 }, isPending: false, isError: false })

    const { getByRole, getByPlaceholder } = await render(<SubdivisionWizard />)

    // Step 1: select a subdivision, advance.
    await userEvent.click(getByRole('combobox'))
    await userEvent.click(getByRole('option', { name: 'SUB01 - Downtown' }))
    await userEvent.click(getByRole('button', { name: /^Next$/i }))

    // Step 2: fill the category name, then go Back to step 1.
    await userEvent.fill(getByPlaceholder('Enter category name'), 'TestCat')
    await userEvent.click(getByRole('button', { name: /Back/i }))

    // Come back to step 2 — the value must persist (form state retained).
    await userEvent.click(getByRole('button', { name: /^Next$/i }))
    await expect.element(getByPlaceholder('Enter category name')).toHaveValue('TestCat')
  })
})
