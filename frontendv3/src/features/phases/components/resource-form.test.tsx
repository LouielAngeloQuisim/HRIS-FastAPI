import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import { ResourceForm } from './resource-form'

const { createMock, updateMock } = vi.hoisted(() => ({
  createMock: { mutateAsync: vi.fn() },
  updateMock: { mutateAsync: vi.fn() },
}))
vi.mock('@/lib/api/phases', () => ({
  useCreatePhase: () => createMock,
  useUpdatePhase: () => updateMock,
}))

const { useSubdivisionsMock } = vi.hoisted(() => ({
  useSubdivisionsMock: vi.fn(),
}))
vi.mock('@/lib/api/subdivisions', () => ({
  useSubdivisions: (...args: unknown[]) => useSubdivisionsMock(...args),
}))

vi.mock('@/context/permissions-provider', () => ({
  useCan: () => true,
}))

describe('Phases ResourceForm', () => {
  it('renders form and calls create mutation with correct payload', async () => {
    useSubdivisionsMock.mockReturnValue({
      data: { data: [], count: 0 },
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })
    createMock.mutateAsync.mockResolvedValue({})
    const onClose = vi.fn()

    const screen = await render(
      <ResourceForm item={null} open={true} onClose={onClose} />
    )

    await expect.element(screen.getByText('Create Phase')).toBeVisible()

    // Sheet renders in a portal; search the whole document for inputs
    const inputs = document.querySelectorAll('input')
    const textInputs = [...inputs].filter(
      (el) => (el as HTMLInputElement).type === 'text'
    )
    expect(textInputs.length).toBeGreaterThanOrEqual(2)

    await userEvent.type(textInputs[1] as HTMLElement, 'Phase 1')
    await userEvent.type(textInputs[2] as HTMLElement, 'Desc')

    const submitBtn = [...document.querySelectorAll('button')].find(
      (b) => b.textContent?.trim() === 'Create'
    )
    expect(submitBtn).toBeDefined()
    await userEvent.click(submitBtn as HTMLElement)

    expect(createMock.mutateAsync).toHaveBeenCalled()
    const payload = createMock.mutateAsync.mock.calls[0][0]
    expect(payload.name).toBe('Phase 1')
    expect(payload.description).toBe('Desc')
  })

  it('passes subdivision query to SelectDropdown for population', async () => {
    useSubdivisionsMock.mockReturnValue({
      data: { data: [], count: 0 },
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })

    const screen = await render(
      <ResourceForm item={null} open={true} onClose={() => {}} />
    )

    await expect.element(screen.getByText('Create Phase')).toBeVisible()
    await expect.element(screen.getByText('Select subdivision')).toBeVisible()
  })
})
