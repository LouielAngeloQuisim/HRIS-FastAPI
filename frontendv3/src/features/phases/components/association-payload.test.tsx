import { it, expect, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import { ResourceForm } from './resource-form'
const { mutateAsync } = vi.hoisted(() => ({ mutateAsync: vi.fn().mockResolvedValue({}) }))
vi.mock('@/lib/api/phases', () => ({ useCreatePhase: () => ({ mutateAsync }), useUpdatePhase: () => ({ mutateAsync }) }))
vi.mock('@/lib/api/subdivisions', () => ({ useSubdivisions: () => ({ data: { data: [{ id: 'parent', name: 'Parent', block_name: 'Parent' }] }, isPending: false }) }))
it('sends the selected parent IDs and backend field names', async () => {
  const onClose = vi.fn()
  const screen = await render(<ResourceForm item={null} open={true} onClose={onClose} />)
  await userEvent.type(screen.getByTestId('phase-code-input'), 'P')
  await userEvent.type(screen.getByTestId('phase-name-input'), 'Phase')
  await userEvent.click(screen.getByTestId('phase-subdivision-select'))
  await userEvent.click(screen.getByRole('option', { name: 'Parent', exact: true }))
  await userEvent.click(screen.getByTestId('phase-submit-button'))
  expect(mutateAsync).toHaveBeenCalledWith(expect.objectContaining({"code": "P", "name": "Phase", "subdivision_id": "parent"}))
  expect(onClose).toHaveBeenCalledOnce()
})
